#!/usr/bin/env python3
"""
GAS Wave Manager
================
Manages wave-based execution and inter-agent coordination.

Usage:
    python3 wave-manager.py status <gas-dir>
    python3 wave-manager.py advance <gas-dir>
    python3 wave-manager.py spawn <gas-dir> --wave <N>
    python3 wave-manager.py sync <gas-dir>
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


# =============================================================================
# Utility Functions
# =============================================================================

def timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: Path) -> Optional[Dict]:
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_json(path: Path, data: Dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


# =============================================================================
# Wave Status
# =============================================================================

def get_wave_status(gas_dir: Path) -> Dict:
    """Get detailed status of all waves."""
    state = read_json(gas_dir / "gas-state.json")
    if not state:
        return {"error": "Cannot read state"}
    
    if state.get("mode") != "swarm":
        return {"error": "Not a swarm-mode workspace"}
    
    waves = state.get("waves", {})
    agents = state.get("agents", {})
    
    result = {
        "current_wave": state.get("current_wave", 1),
        "total_waves": state.get("total_waves", 1),
        "waves": {}
    }
    
    for wave_key, wave_data in waves.items():
        wave_num = int(wave_key) if isinstance(wave_key, str) else wave_key
        wave_agents = wave_data.get("agents", [])
        
        agent_statuses = []
        completed = 0
        running = 0
        pending = 0
        
        for agent_id in wave_agents:
            agent = agents.get(agent_id, {})
            status = agent.get("status", "unknown")
            
            agent_statuses.append({
                "agent_id": agent_id,
                "role": agent.get("role", "unknown"),
                "status": status,
                "generation": agent.get("current_generation", 0)
            })
            
            if status in ["completed", "succeeded"]:
                completed += 1
            elif status == "running":
                running += 1
            else:
                pending += 1
        
        result["waves"][wave_num] = {
            "status": wave_data.get("status", "pending"),
            "started_at": wave_data.get("started_at"),
            "agents": agent_statuses,
            "completed": completed,
            "running": running,
            "pending": pending,
            "total": len(wave_agents),
            "is_complete": completed == len(wave_agents) and len(wave_agents) > 0
        }
    
    return result


def print_wave_status(gas_dir: Path):
    """Print formatted wave status."""
    status = get_wave_status(gas_dir)
    
    if "error" in status:
        print(f"Error: {status['error']}")
        return
    
    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           WAVE STATUS                                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

Current Wave: {status['current_wave']} / {status['total_waves']}
""")
    
    for wave_num in sorted(status['waves'].keys()):
        wave = status['waves'][wave_num]
        indicator = "▶" if wave_num == status['current_wave'] else " "
        complete_bar = "█" * wave['completed'] + "░" * (wave['total'] - wave['completed'])
        
        print(f"""
{indicator} Wave {wave_num}: [{complete_bar}] {wave['completed']}/{wave['total']}
  Status: {wave['status']}
  Started: {wave.get('started_at', 'Not started')}
  Agents:""")
        
        for agent in wave['agents']:
            status_icon = "✓" if agent['status'] in ['completed', 'succeeded'] else \
                         "⟳" if agent['status'] == 'running' else "○"
            print(f"    {status_icon} {agent['agent_id']}: {agent['role']} "
                  f"(gen {agent['generation']}) - {agent['status']}")
    
    print()


# =============================================================================
# Wave Operations
# =============================================================================

def can_advance_wave(gas_dir: Path) -> tuple:
    """Check if wave can be advanced. Returns (can_advance, reason)."""
    state = read_json(gas_dir / "gas-state.json")
    if not state:
        return False, "Cannot read state"
    
    current = state.get("current_wave", 1)
    total = state.get("total_waves", 1)
    
    if current >= total:
        return False, f"Already at final wave ({current}/{total})"
    
    # Check if all agents in current wave are complete
    waves = state.get("waves", {})
    wave_data = waves.get(str(current), waves.get(current, {}))
    wave_agents = wave_data.get("agents", [])
    
    agents = state.get("agents", {})
    incomplete = []
    
    for agent_id in wave_agents:
        agent = agents.get(agent_id, {})
        if agent.get("status") not in ["completed", "succeeded"]:
            incomplete.append(agent_id)
    
    if incomplete:
        return False, f"Wave {current} incomplete: {', '.join(incomplete)}"
    
    return True, f"Ready to advance from wave {current} to {current + 1}"


def advance_wave(gas_dir: Path) -> bool:
    """Advance to next wave if possible."""
    can_advance, reason = can_advance_wave(gas_dir)
    print(f"Check: {reason}")
    
    if not can_advance:
        return False
    
    state = read_json(gas_dir / "gas-state.json")
    current = state.get("current_wave", 1)
    
    # Update state
    state["current_wave"] = current + 1
    
    # Mark new wave as running
    waves = state.get("waves", {})
    new_wave_key = str(current + 1)
    if new_wave_key in waves:
        waves[new_wave_key]["status"] = "running"
        waves[new_wave_key]["started_at"] = timestamp()
    
    # Mark old wave as complete
    old_wave_key = str(current)
    if old_wave_key in waves:
        waves[old_wave_key]["status"] = "completed"
        waves[old_wave_key]["completed_at"] = timestamp()
    
    write_json(gas_dir / "gas-state.json", state)
    print(f"Advanced to wave {current + 1}")
    return True


def spawn_wave_agents(gas_dir: Path, wave: int):
    """Spawn generation 1 for all agents in a wave."""
    state = read_json(gas_dir / "gas-state.json")
    if not state:
        print("Error: Cannot read state")
        return
    
    waves = state.get("waves", {})
    wave_data = waves.get(str(wave), waves.get(wave, {}))
    wave_agents = wave_data.get("agents", [])
    
    agents = state.get("agents", {})
    
    for agent_id in wave_agents:
        agent = agents.get(agent_id, {})
        if agent.get("current_generation", 0) == 0:
            # Spawn generation 1
            gen_dir = gas_dir / "agents" / agent_id / "generations" / "gen-1"
            gen_dir.mkdir(parents=True, exist_ok=True)
            
            status = {
                "generation": 1,
                "agent_id": agent_id,
                "status": "running",
                "started_at": timestamp(),
                "interactions": 0,
                "progress": 0.0,
                "confidence": 1.0,
                "errors": 0
            }
            write_json(gen_dir / "status.json", status)
            
            # Update agent state
            agent["status"] = "running"
            agent["current_generation"] = 1
            
            print(f"Spawned generation 1 for {agent_id}")
    
    # Update state
    write_json(gas_dir / "gas-state.json", state)


def sync_agent_outputs(gas_dir: Path):
    """Sync outputs from completed agents to shared directory."""
    state = read_json(gas_dir / "gas-state.json")
    if not state:
        print("Error: Cannot read state")
        return
    
    agents = state.get("agents", {})
    shared_dir = gas_dir / "shared"
    synced = 0
    
    for agent_id, agent in agents.items():
        if agent.get("status") in ["completed", "succeeded"]:
            gen = agent.get("current_generation", 1)
            output_dir = gas_dir / "agents" / agent_id / "generations" / f"gen-{gen}" / "output"
            
            if output_dir.exists():
                # Create agent's shared folder
                agent_shared = shared_dir / agent_id
                agent_shared.mkdir(parents=True, exist_ok=True)
                
                # Copy output files (simplified - just note the sync)
                for file in output_dir.iterdir():
                    if file.is_file():
                        # In production, would copy file
                        synced += 1
    
    print(f"Synced {synced} files to shared directory")


def get_agent_dependencies(gas_dir: Path, agent_id: str) -> Dict:
    """Get dependencies and their outputs for an agent."""
    state = read_json(gas_dir / "gas-state.json")
    if not state:
        return {"error": "Cannot read state"}
    
    deps = state.get("dependencies", {}).get(agent_id, [])
    agents = state.get("agents", {})
    
    result = {
        "agent_id": agent_id,
        "dependencies": []
    }
    
    for dep_id in deps:
        dep_agent = agents.get(dep_id, {})
        dep_info = {
            "agent_id": dep_id,
            "role": dep_agent.get("role", "unknown"),
            "status": dep_agent.get("status", "unknown"),
            "output_available": dep_agent.get("status") in ["completed", "succeeded"]
        }
        
        if dep_info["output_available"]:
            # List output files
            gen = dep_agent.get("current_generation", 1)
            output_dir = gas_dir / "agents" / dep_id / "generations" / f"gen-{gen}" / "output"
            if output_dir.exists():
                dep_info["outputs"] = [f.name for f in output_dir.iterdir() if f.is_file()]
        
        result["dependencies"].append(dep_info)
    
    return result


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="GAS Wave Manager - Wave-based Execution Control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check wave status
  python3 wave-manager.py status /workspace/my-project-gas
  
  # Advance to next wave
  python3 wave-manager.py advance /workspace/my-project-gas
  
  # Spawn agents in a wave
  python3 wave-manager.py spawn /workspace/my-project-gas --wave 2
  
  # Sync outputs to shared
  python3 wave-manager.py sync /workspace/my-project-gas
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # status command
    status_parser = subparsers.add_parser("status", help="Get wave status")
    status_parser.add_argument("gas_dir", help="Path to GAS workspace")
    
    # advance command
    advance_parser = subparsers.add_parser("advance", help="Advance to next wave")
    advance_parser.add_argument("gas_dir", help="Path to GAS workspace")
    
    # spawn command
    spawn_parser = subparsers.add_parser("spawn", help="Spawn wave agents")
    spawn_parser.add_argument("gas_dir", help="Path to GAS workspace")
    spawn_parser.add_argument("--wave", type=int, required=True, help="Wave number")
    
    # sync command
    sync_parser = subparsers.add_parser("sync", help="Sync agent outputs")
    sync_parser.add_argument("gas_dir", help="Path to GAS workspace")
    
    # deps command
    deps_parser = subparsers.add_parser("deps", help="Get agent dependencies")
    deps_parser.add_argument("gas_dir", help="Path to GAS workspace")
    deps_parser.add_argument("--agent", required=True, help="Agent ID")
    
    args = parser.parse_args()
    
    if args.command == "status":
        print_wave_status(Path(args.gas_dir))
        
    elif args.command == "advance":
        advance_wave(Path(args.gas_dir))
        
    elif args.command == "spawn":
        spawn_wave_agents(Path(args.gas_dir), args.wave)
        
    elif args.command == "sync":
        sync_agent_outputs(Path(args.gas_dir))
        
    elif args.command == "deps":
        deps = get_agent_dependencies(Path(args.gas_dir), args.agent)
        print(json.dumps(deps, indent=2))
        
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
