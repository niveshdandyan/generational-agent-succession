#!/usr/bin/env python3
"""
GAS Swarm Orchestrator
======================
Coordinates parallel agent swarms with wave-based execution.

Usage:
    python3 swarm-orchestrator.py init <project-name> <task-objective> <agent-count>
    python3 swarm-orchestrator.py decompose <gas-dir> <task-description>
    python3 swarm-orchestrator.py run <gas-dir>
    python3 swarm-orchestrator.py status <gas-dir>
"""

import os
import sys
import json
import argparse
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import from sibling scripts
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# Try to import knowledge_store, fall back to inline if not available
try:
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location("knowledge_store", SCRIPT_DIR / "knowledge-store.py")
    knowledge_store = module_from_spec(spec)
    spec.loader.exec_module(knowledge_store)
    read_store = knowledge_store.read_store
    write_store = knowledge_store.write_store
    add_pattern = knowledge_store.add_pattern
except Exception:
    # Fallback - functions not needed for core functionality
    read_store = None
    write_store = None
    add_pattern = None


# =============================================================================
# Configuration
# =============================================================================

DEFAULT_CONFIG = {
    "workspace_base": os.getenv("WORKSPACE_BASE", "/workspace"),
    "max_parallel_agents": 12,
    "min_agents": 2,
    "default_agents": 4,
    "wave_poll_interval": 5,  # seconds
    "agent_timeout": 3600,  # 1 hour max per wave
}


# =============================================================================
# Utility Functions
# =============================================================================

def timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def log(message: str, level: str = "INFO"):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {message}")


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


def slugify(name: str) -> str:
    return name.lower().replace(' ', '-').replace('_', '-')


# =============================================================================
# Task Decomposition
# =============================================================================

def decompose_task(task_objective: str, num_agents: int) -> Dict:
    """
    Decompose a task into parallel components.
    Returns a wave-based execution plan.
    
    This is a heuristic decomposition - in practice, an LLM would do this.
    """
    # Default decomposition pattern for common project types
    common_roles = [
        {"role": "core-architect", "wave": 1, "focus": "Project structure, core abstractions, interfaces"},
        {"role": "database-engineer", "wave": 2, "focus": "Schema, migrations, data access layer"},
        {"role": "backend-api", "wave": 2, "focus": "API endpoints, business logic, validation"},
        {"role": "auth-engineer", "wave": 2, "focus": "Authentication, authorization, security"},
        {"role": "frontend-ui", "wave": 3, "focus": "User interface, components, state management"},
        {"role": "integration-lead", "wave": 4, "focus": "Integration, testing, deployment"},
    ]
    
    # Assign agents based on count
    assigned = []
    for i, role in enumerate(common_roles[:num_agents]):
        assigned.append({
            "agent_id": f"agent-{i+1}",
            "role": role["role"],
            "wave": role["wave"],
            "focus": role["focus"],
            "status": "pending",
            "current_generation": 0,
            "total_generations": 0
        })
    
    # Organize into waves
    waves = {}
    for agent in assigned:
        wave_num = agent["wave"]
        if wave_num not in waves:
            waves[wave_num] = {"agents": [], "status": "pending", "started_at": None}
        waves[wave_num]["agents"].append(agent["agent_id"])
    
    return {
        "task_objective": task_objective,
        "decomposed_at": timestamp(),
        "total_agents": len(assigned),
        "total_waves": len(waves),
        "agents": {a["agent_id"]: a for a in assigned},
        "waves": waves,
        "dependencies": generate_dependencies(assigned)
    }


def generate_dependencies(agents: List[Dict]) -> Dict:
    """Generate wave-based dependencies."""
    deps = {}
    waves = {}
    
    for agent in agents:
        wave = agent["wave"]
        if wave not in waves:
            waves[wave] = []
        waves[wave].append(agent["agent_id"])
    
    for agent in agents:
        wave = agent["wave"]
        if wave > 1:
            # Depends on all agents from previous wave
            deps[agent["agent_id"]] = waves.get(wave - 1, [])
        else:
            deps[agent["agent_id"]] = []
    
    return deps


# =============================================================================
# Swarm Initialization
# =============================================================================

def init_swarm(project_name: str, task_objective: str, 
               num_agents: int = 4) -> Path:
    """Initialize a swarm-mode GAS workspace."""
    project_slug = slugify(project_name)
    gas_dir = Path(DEFAULT_CONFIG["workspace_base"]) / f"{project_slug}-gas"
    
    log(f"Initializing swarm workspace: {gas_dir}")
    log(f"Agents: {num_agents}")
    
    # Create directories
    (gas_dir / "generations").mkdir(parents=True, exist_ok=True)
    (gas_dir / "knowledge").mkdir(parents=True, exist_ok=True)
    (gas_dir / "output").mkdir(parents=True, exist_ok=True)
    (gas_dir / "shared").mkdir(parents=True, exist_ok=True)
    (gas_dir / "agents").mkdir(parents=True, exist_ok=True)
    
    # Decompose task
    decomposition = decompose_task(task_objective, num_agents)
    
    # Initialize state
    state = {
        "project_name": project_name,
        "project_slug": project_slug,
        "version": "2.0.1",
        "start_time": timestamp(),
        "mode": "swarm",
        "task_objective": task_objective,
        "status": "initialized",
        "current_wave": 1,
        "total_waves": decomposition["total_waves"],
        "agents": decomposition["agents"],
        "waves": decomposition["waves"],
        "dependencies": decomposition["dependencies"],
        "knowledge_store": "knowledge/store.json"
    }
    write_json(gas_dir / "gas-state.json", state)
    
    # Initialize knowledge store
    knowledge = {
        "project": project_slug,
        "created": timestamp(),
        "last_updated": timestamp(),
        "generations_completed": 0,
        "success_patterns": [],
        "anti_patterns": [],
        "domain_knowledge": [],
        "agent_contributions": {}
    }
    write_json(gas_dir / "knowledge" / "store.json", knowledge)
    
    # Create agent directories
    for agent_id, agent_info in decomposition["agents"].items():
        agent_dir = gas_dir / "agents" / agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)
        
        # Agent config
        config = {
            "agent_id": agent_id,
            "role": agent_info["role"],
            "focus": agent_info["focus"],
            "wave": agent_info["wave"],
            "created_at": timestamp()
        }
        write_json(agent_dir / "config.json", config)
    
    log(f"Swarm initialized: {num_agents} agents across {decomposition['total_waves']} waves")
    return gas_dir


# =============================================================================
# Wave Execution
# =============================================================================

class WaveManager:
    """Manages wave-based execution of agent swarms."""
    
    def __init__(self, gas_dir: Path):
        self.gas_dir = gas_dir
        self.state = read_json(gas_dir / "gas-state.json")
        self._lock = threading.Lock()
    
    def get_current_wave(self) -> int:
        return self.state.get("current_wave", 1)
    
    def get_wave_agents(self, wave: int) -> List[str]:
        """Get agents in a specific wave."""
        waves = self.state.get("waves", {})
        wave_data = waves.get(str(wave), waves.get(wave, {}))
        return wave_data.get("agents", [])
    
    def is_wave_complete(self, wave: int) -> bool:
        """Check if all agents in a wave have completed."""
        agents = self.get_wave_agents(wave)
        for agent_id in agents:
            agent = self.state.get("agents", {}).get(agent_id, {})
            if agent.get("status") not in ["completed", "succeeded"]:
                return False
        return True
    
    def advance_wave(self) -> bool:
        """Try to advance to next wave. Returns True if advanced."""
        current = self.get_current_wave()
        total = self.state.get("total_waves", 1)
        
        if current >= total:
            return False
        
        if not self.is_wave_complete(current):
            return False
        
        with self._lock:
            self.state["current_wave"] = current + 1
            waves = self.state.get("waves", {})
            wave_key = str(current + 1)
            if wave_key in waves or current + 1 in waves:
                wave_data = waves.get(wave_key, waves.get(current + 1, {}))
                wave_data["status"] = "running"
                wave_data["started_at"] = timestamp()
            
            write_json(self.gas_dir / "gas-state.json", self.state)
            
        log(f"Advanced to wave {current + 1}")
        return True
    
    def update_agent_status(self, agent_id: str, status: str, 
                            generation: int = None):
        """Update an agent's status."""
        with self._lock:
            if agent_id in self.state.get("agents", {}):
                self.state["agents"][agent_id]["status"] = status
                if generation:
                    self.state["agents"][agent_id]["current_generation"] = generation
                self.state["agents"][agent_id]["last_updated"] = timestamp()
                write_json(self.gas_dir / "gas-state.json", self.state)
    
    def spawn_agent_generation(self, agent_id: str, generation: int) -> Path:
        """Spawn a new generation for an agent."""
        gen_dir = self.gas_dir / "agents" / agent_id / "generations" / f"gen-{generation}"
        gen_dir.mkdir(parents=True, exist_ok=True)
        
        # Get agent config
        agent_config = read_json(self.gas_dir / "agents" / agent_id / "config.json") or {}
        
        # Create generation status
        status = {
            "generation": generation,
            "agent_id": agent_id,
            "role": agent_config.get("role", "general"),
            "focus": agent_config.get("focus", ""),
            "status": "running",
            "started_at": timestamp(),
            "interactions": 0,
            "progress": 0.0,
            "confidence": 1.0,
            "errors": 0,
            "learnings": []
        }
        write_json(gen_dir / "status.json", status)
        
        self.update_agent_status(agent_id, "running", generation)
        log(f"Spawned generation {generation} for {agent_id}")
        
        return gen_dir
    
    def check_all_complete(self) -> bool:
        """Check if all agents across all waves are complete."""
        for agent_id, agent in self.state.get("agents", {}).items():
            if agent.get("status") not in ["completed", "succeeded"]:
                return False
        return True
    
    def get_status_summary(self) -> Dict:
        """Get a summary of swarm status."""
        agents = self.state.get("agents", {})
        
        by_status = {}
        for agent_id, agent in agents.items():
            status = agent.get("status", "unknown")
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "current_wave": self.get_current_wave(),
            "total_waves": self.state.get("total_waves", 1),
            "total_agents": len(agents),
            "by_status": by_status,
            "is_complete": self.check_all_complete()
        }


# =============================================================================
# Swarm Execution
# =============================================================================

def run_swarm(gas_dir: Path):
    """Run the swarm orchestrator main loop."""
    log(f"Starting swarm orchestrator for: {gas_dir}")
    
    manager = WaveManager(gas_dir)
    state = manager.state
    
    if not state or state.get("mode") != "swarm":
        raise RuntimeError("Not a swarm-mode workspace")
    
    log(f"Total agents: {len(state.get('agents', {}))}")
    log(f"Total waves: {state.get('total_waves', 1)}")
    
    # Spawn generation 1 for all wave-1 agents
    wave_1_agents = manager.get_wave_agents(1)
    for agent_id in wave_1_agents:
        agent = state.get("agents", {}).get(agent_id, {})
        if agent.get("current_generation", 0) == 0:
            manager.spawn_agent_generation(agent_id, 1)
    
    # Mark wave 1 as running
    if "1" in state.get("waves", {}) or 1 in state.get("waves", {}):
        wave_data = state["waves"].get("1", state["waves"].get(1, {}))
        wave_data["status"] = "running"
        wave_data["started_at"] = timestamp()
        write_json(gas_dir / "gas-state.json", state)
    
    # Main monitoring loop
    running = True
    while running:
        try:
            # Refresh state
            manager.state = read_json(gas_dir / "gas-state.json")
            
            # Check completion
            if manager.check_all_complete():
                log("All agents completed!")
                generate_swarm_report(gas_dir)
                running = False
                break
            
            # Try to advance wave
            manager.advance_wave()
            
            # Spawn new generations for current wave if needed
            current_wave = manager.get_current_wave()
            wave_agents = manager.get_wave_agents(current_wave)
            
            for agent_id in wave_agents:
                agent = manager.state.get("agents", {}).get(agent_id, {})
                if agent.get("current_generation", 0) == 0:
                    manager.spawn_agent_generation(agent_id, 1)
            
            # Log status
            summary = manager.get_status_summary()
            log(f"Wave {summary['current_wave']}/{summary['total_waves']} | "
                f"Status: {summary['by_status']}")
            
            time.sleep(DEFAULT_CONFIG["wave_poll_interval"])
            
        except KeyboardInterrupt:
            log("Interrupted, stopping...")
            running = False
        except Exception as e:
            log(f"Error: {e}", "ERROR")
            time.sleep(5)
    
    log("Swarm orchestrator stopped")


def generate_swarm_report(gas_dir: Path) -> str:
    """Generate final swarm report."""
    state = read_json(gas_dir / "gas-state.json")
    knowledge = read_json(gas_dir / "knowledge" / "store.json")
    
    if not state:
        return "Error: Cannot read state"
    
    # Calculate stats
    agents = state.get("agents", {})
    total_generations = sum(a.get("total_generations", 0) for a in agents.values())
    
    report = f"""
================================================================================
                       GAS SWARM COMPLETION REPORT
================================================================================

Project: {state.get('project_name', 'Unknown')}
Mode: Swarm ({len(agents)} agents, {state.get('total_waves', 0)} waves)
Started: {state.get('start_time', 'Unknown')}

--------------------------------------------------------------------------------
AGENT SUMMARY
--------------------------------------------------------------------------------
"""
    
    for agent_id, agent in agents.items():
        report += f"""
Agent: {agent_id}
  Role: {agent.get('role', 'Unknown')}
  Wave: {agent.get('wave', 0)}
  Generations: {agent.get('total_generations', 0)}
  Status: {agent.get('status', 'Unknown')}
"""
    
    report += f"""
--------------------------------------------------------------------------------
KNOWLEDGE ACCUMULATED
--------------------------------------------------------------------------------
Success Patterns: {len(knowledge.get('success_patterns', [])) if knowledge else 0}
Anti-Patterns: {len(knowledge.get('anti_patterns', [])) if knowledge else 0}
Domain Insights: {len(knowledge.get('domain_knowledge', [])) if knowledge else 0}
Total Generations: {total_generations}

================================================================================
"""
    
    report_path = gas_dir / "SWARM_REPORT.md"
    with open(report_path, 'w') as f:
        f.write(report)
    
    log(f"Report written to: {report_path}")
    print(report)
    return report


def get_swarm_status(gas_dir: Path):
    """Print swarm status."""
    manager = WaveManager(gas_dir)
    summary = manager.get_status_summary()
    
    print(f"""
================================================================================
                           SWARM STATUS
================================================================================

Current Wave: {summary['current_wave']} / {summary['total_waves']}
Total Agents: {summary['total_agents']}
All Complete: {summary['is_complete']}

Status Breakdown:
""")
    
    for status, count in summary['by_status'].items():
        print(f"  {status}: {count}")
    
    print("\nAgents:")
    for agent_id, agent in manager.state.get("agents", {}).items():
        print(f"  [{agent.get('wave', '?')}] {agent_id}: {agent.get('status', 'unknown')} "
              f"(gen {agent.get('current_generation', 0)})")
    
    print("=" * 80)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="GAS Swarm Orchestrator - Parallel Agent Coordination",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize a swarm with 4 agents
  python3 swarm-orchestrator.py init "My Project" "Build web app" 4
  
  # Run the swarm
  python3 swarm-orchestrator.py run /workspace/my-project-gas
  
  # Check status
  python3 swarm-orchestrator.py status /workspace/my-project-gas
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # init command
    init_parser = subparsers.add_parser("init", help="Initialize swarm workspace")
    init_parser.add_argument("project_name", help="Project name")
    init_parser.add_argument("task_objective", help="Task objective")
    init_parser.add_argument("agent_count", type=int, nargs="?", default=4,
                            help="Number of agents (default: 4)")
    
    # run command
    run_parser = subparsers.add_parser("run", help="Run swarm orchestrator")
    run_parser.add_argument("gas_dir", help="Path to GAS workspace")
    
    # status command
    status_parser = subparsers.add_parser("status", help="Get swarm status")
    status_parser.add_argument("gas_dir", help="Path to GAS workspace")
    
    # report command
    report_parser = subparsers.add_parser("report", help="Generate report")
    report_parser.add_argument("gas_dir", help="Path to GAS workspace")
    
    args = parser.parse_args()
    
    if args.command == "init":
        gas_dir = init_swarm(args.project_name, args.task_objective, args.agent_count)
        print(f"\nSwarm initialized: {gas_dir}")
        print(f"\nRun with: python3 {__file__} run {gas_dir}")
        
    elif args.command == "run":
        run_swarm(Path(args.gas_dir))
        
    elif args.command == "status":
        get_swarm_status(Path(args.gas_dir))
        
    elif args.command == "report":
        generate_swarm_report(Path(args.gas_dir))
        
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
