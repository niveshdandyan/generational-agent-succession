#!/usr/bin/env python3
"""
GAS Orchestrator - Main coordination script for Generational Agent Succession
==============================================================================
Coordinates workspace initialization, agent spawning, monitoring, and succession.

Usage:
    python3 gas-orchestrator.py init <project-name> <task-objective>
    python3 gas-orchestrator.py run <gas-dir> [--mode=single|swarm]
    python3 gas-orchestrator.py status <gas-dir>
    python3 gas-orchestrator.py spawn <gas-dir> [--generation=N] [--agent=agent-id]
    python3 gas-orchestrator.py report <gas-dir>
"""

import os
import sys
import json
import argparse
import subprocess
import time
import signal
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# =============================================================================
# Configuration
# =============================================================================

DEFAULT_CONFIG = {
    "workspace_base": os.getenv("WORKSPACE_BASE", "/workspace"),
    "max_generations_per_agent": 10,
    "max_total_generations": 50,
    "poll_interval_seconds": 30,
    "triggers": {
        "interaction_limit": 150,
        "confidence_threshold": 0.70,
        "error_rate_threshold": 0.15,
        "stall_minutes": 10
    },
    "mode": "single"  # single or swarm
}

SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATES_DIR = SKILL_DIR / "templates"
RESOURCES_DIR = SKILL_DIR / "resources"


# =============================================================================
# Utility Functions
# =============================================================================

def log(message: str, level: str = "INFO"):
    """Log with timestamp."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def read_json(path: Path) -> Optional[Dict]:
    """Read JSON file safely."""
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        log(f"Error reading {path}: {e}", "ERROR")
        return None


def write_json(path: Path, data: Dict):
    """Write JSON file with formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(name: str) -> str:
    """Convert project name to slug."""
    return name.lower().replace(' ', '-').replace('_', '-')


# =============================================================================
# Workspace Management
# =============================================================================

def init_workspace(project_name: str, task_objective: str, mode: str = "single") -> Path:
    """Initialize a new GAS workspace."""
    project_slug = slugify(project_name)
    gas_dir = Path(DEFAULT_CONFIG["workspace_base"]) / f"{project_slug}-gas"
    
    log(f"Initializing GAS workspace: {gas_dir}")
    
    # Create directory structure
    (gas_dir / "generations").mkdir(parents=True, exist_ok=True)
    (gas_dir / "knowledge").mkdir(parents=True, exist_ok=True)
    (gas_dir / "output").mkdir(parents=True, exist_ok=True)
    (gas_dir / "shared").mkdir(parents=True, exist_ok=True)
    
    if mode == "swarm":
        (gas_dir / "agents").mkdir(parents=True, exist_ok=True)
    
    # Initialize GAS state
    state = {
        "project_name": project_name,
        "project_slug": project_slug,
        "version": "2.0.1",
        "start_time": timestamp(),
        "mode": mode,
        "task_objective": task_objective,
        "current_generation": 0,
        "total_generations": 0,
        "status": "initialized",
        "agents": {} if mode == "swarm" else None,
        "waves": {} if mode == "swarm" else None,
        "current_wave": 0 if mode == "swarm" else None,
        "knowledge_store": "knowledge/store.json"
    }
    write_json(gas_dir / "gas-state.json", state)
    
    # Initialize knowledge store
    knowledge_store = {
        "project": project_slug,
        "created": timestamp(),
        "last_updated": timestamp(),
        "generations_completed": 0,
        "success_patterns": [],
        "anti_patterns": [],
        "domain_knowledge": [],
        "agent_contributions": {} if mode == "swarm" else None
    }
    write_json(gas_dir / "knowledge" / "store.json", knowledge_store)
    
    log(f"Workspace initialized at: {gas_dir}")
    return gas_dir


# =============================================================================
# Generation Management
# =============================================================================

def get_current_generation(gas_dir: Path, agent_id: Optional[str] = None) -> int:
    """Get current generation number."""
    state = read_json(gas_dir / "gas-state.json")
    if not state:
        return 0
    
    if agent_id and state.get("agents"):
        return state["agents"].get(agent_id, {}).get("current_generation", 0)
    return state.get("current_generation", 0)


def spawn_generation(gas_dir: Path, generation: int, agent_id: Optional[str] = None, 
                     transfer_doc: Optional[Dict] = None) -> Dict:
    """Spawn a new generation of an agent."""
    state = read_json(gas_dir / "gas-state.json")
    if not state:
        raise RuntimeError(f"Cannot read GAS state from {gas_dir}")
    
    # Determine generation directory
    if agent_id:
        gen_dir = gas_dir / "agents" / agent_id / "generations" / f"gen-{generation}"
    else:
        gen_dir = gas_dir / "generations" / f"gen-{generation}"
    
    gen_dir.mkdir(parents=True, exist_ok=True)
    
    # Create generation status
    gen_status = {
        "generation": generation,
        "agent_id": agent_id,
        "status": "pending",
        "started_at": None,
        "last_updated": timestamp(),
        "interactions": 0,
        "progress": 0.0,
        "current_task": "Waiting to start",
        "completed_tasks": [],
        "confidence": 1.0,
        "errors": 0,
        "learnings": [],
        "parent_generation": generation - 1 if generation > 1 else None,
        "transfer_document": "transfer.json" if transfer_doc else None
    }
    write_json(gen_dir / "status.json", gen_status)
    
    # Save transfer document if provided
    if transfer_doc:
        write_json(gen_dir / "transfer.json", transfer_doc)
    
    # Update GAS state
    if agent_id and state.get("agents"):
        state["agents"][agent_id]["current_generation"] = generation
        state["agents"][agent_id]["total_generations"] = max(
            state["agents"][agent_id].get("total_generations", 0), generation
        )
    else:
        state["current_generation"] = generation
        state["total_generations"] = max(state.get("total_generations", 0), generation)
    
    state["last_updated"] = timestamp()
    write_json(gas_dir / "gas-state.json", state)
    
    log(f"Spawned generation {generation}" + (f" for agent {agent_id}" if agent_id else ""))
    
    return {
        "generation": generation,
        "agent_id": agent_id,
        "directory": str(gen_dir),
        "status_file": str(gen_dir / "status.json")
    }


def render_generation_prompt(gas_dir: Path, generation: int, 
                             agent_id: Optional[str] = None) -> str:
    """Render the generation prompt template with variables."""
    state = read_json(gas_dir / "gas-state.json")
    knowledge = read_json(gas_dir / "knowledge" / "store.json")
    
    if not state:
        raise RuntimeError("Cannot read GAS state")
    
    # Determine paths
    if agent_id:
        gen_dir = gas_dir / "agents" / agent_id / "generations" / f"gen-{generation}"
    else:
        gen_dir = gas_dir / "generations" / f"gen-{generation}"
    
    # Load transfer document if exists
    transfer_doc = None
    parent_gen = generation - 1
    if parent_gen >= 1:
        if agent_id:
            parent_dir = gas_dir / "agents" / agent_id / "generations" / f"gen-{parent_gen}"
        else:
            parent_dir = gas_dir / "generations" / f"gen-{parent_gen}"
        
        transfer_path = parent_dir / "transfer.json"
        if transfer_path.exists():
            transfer_doc = read_json(transfer_path)
    
    # Read template
    template_path = TEMPLATES_DIR / "generation-prompt.md"
    with open(template_path, 'r') as f:
        template = f.read()
    
    # Replace variables
    variables = {
        "GENERATION": str(generation),
        "NEXT_GENERATION": str(generation + 1),
        "PARENT_GENERATION": str(parent_gen) if parent_gen >= 1 else "",
        "PROJECT_NAME": state.get("project_name", "Project"),
        "PROJECT_SLUG": state.get("project_slug", "project"),
        "TASK_OBJECTIVE": state.get("task_objective", "Complete the task"),
        "TIMESTAMP": timestamp(),
        "IS_FIRST_GENERATION": str(generation == 1).lower(),
        "WORKSPACE": str(gas_dir),
        "TRANSFER_DOCUMENT": json.dumps(transfer_doc, indent=2) if transfer_doc else "No transfer document",
        "SUCCESS_PATTERNS": format_patterns(knowledge.get("success_patterns", []) if knowledge else []),
        "ANTI_PATTERNS": format_patterns(knowledge.get("anti_patterns", []) if knowledge else []),
        "CURRENT_SUBTASK": "Begin working on the task",
        "REMAINING_SUBTASKS": "[]"
    }
    
    for key, value in variables.items():
        template = template.replace("{{" + key + "}}", value)
    
    # Handle Handlebars conditionals (simplified)
    if generation == 1:
        # Remove else block, keep if block content
        template = remove_else_blocks(template, "IS_FIRST_GENERATION")
    else:
        # Remove if block, keep else block content
        template = keep_else_blocks(template, "IS_FIRST_GENERATION")
    
    return template


def format_patterns(patterns: List[Dict]) -> str:
    """Format patterns for prompt injection."""
    if not patterns:
        return "*No patterns recorded yet.*"
    
    lines = []
    for p in patterns[:10]:  # Limit to top 10
        lines.append(f"- **{p.get('context', 'General')}**: {p.get('pattern', p.get('content', 'N/A'))}")
    return "\n".join(lines)


def remove_else_blocks(template: str, condition: str) -> str:
    """Remove {{else}} blocks for true conditions."""
    # Simple implementation - just remove the condition markers
    template = template.replace(f"{{{{#if {condition}}}}}", "")
    template = template.replace("{{else}}", "<!-- else removed -->")
    template = template.replace("{{/if}}", "")
    return template


def keep_else_blocks(template: str, condition: str) -> str:
    """Keep {{else}} blocks for false conditions."""
    template = template.replace(f"{{{{#if {condition}}}}}", "<!-- if removed -->")
    template = template.replace("{{else}}", "")
    template = template.replace("{{/if}}", "")
    return template


# =============================================================================
# Monitoring & Triggers
# =============================================================================

def check_triggers(gas_dir: Path, generation: int, 
                   agent_id: Optional[str] = None) -> Tuple[bool, str, float]:
    """
    Check if succession should be triggered.
    Returns: (should_handoff, reason, score)
    """
    # Use the check-triggers.py script
    cmd = [sys.executable, str(SCRIPT_DIR / "check-triggers.py"), str(gas_dir)]
    if generation:
        cmd.append(str(generation))
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Parse output
    if result.returncode == 0:
        return False, "none", 0.0
    elif result.returncode == 1:
        return True, "score_warning", 0.55
    elif result.returncode == 2:
        return True, "score_critical", 0.75
    else:
        return False, "error", 0.0


def read_generation_status(gas_dir: Path, generation: int, 
                           agent_id: Optional[str] = None) -> Optional[Dict]:
    """Read status of a specific generation."""
    if agent_id:
        status_path = gas_dir / "agents" / agent_id / "generations" / f"gen-{generation}" / "status.json"
    else:
        status_path = gas_dir / "generations" / f"gen-{generation}" / "status.json"
    
    return read_json(status_path)


def monitor_generation(gas_dir: Path, generation: int, 
                       agent_id: Optional[str] = None) -> str:
    """
    Monitor a running generation.
    Returns: status string (running, completed, needs_succession, failed)
    """
    status = read_generation_status(gas_dir, generation, agent_id)
    if not status:
        return "unknown"
    
    current_status = status.get("status", "unknown")
    
    if current_status in ["completed", "failed", "needs_succession"]:
        return current_status
    
    # Check triggers
    should_handoff, reason, score = check_triggers(gas_dir, generation, agent_id)
    
    if should_handoff:
        log(f"Succession triggered: {reason} (score: {score:.2f})")
        return "needs_succession"
    
    return current_status


# =============================================================================
# Succession Handling
# =============================================================================

def create_transfer_document(gas_dir: Path, generation: int, 
                             agent_id: Optional[str] = None) -> Dict:
    """Create a transfer document from current generation's state."""
    status = read_generation_status(gas_dir, generation, agent_id)
    knowledge = read_json(gas_dir / "knowledge" / "store.json")
    state = read_json(gas_dir / "gas-state.json")
    
    if not status or not state:
        raise RuntimeError("Cannot read status or state")
    
    transfer_doc = {
        "meta": {
            "parent_generation": generation,
            "child_generation": generation + 1,
            "timestamp": timestamp(),
            "reason": status.get("succession_reason", "triggered"),
            "confidence_at_handoff": status.get("confidence", 0.5)
        },
        "task_state": {
            "objective": state.get("task_objective", ""),
            "overall_progress": status.get("progress", 0.0),
            "current_phase": status.get("current_task", ""),
            "remaining_phases": [],
            "blockers": status.get("blockers", [])
        },
        "completed_work": {
            "subtasks": [
                {"name": task, "status": "done"}
                for task in status.get("completed_tasks", [])
            ],
            "key_decisions": status.get("key_decisions", [])
        },
        "working_memory": {
            "active_files": status.get("active_files", []),
            "next_steps": status.get("next_steps", []),
            "environment": {}
        },
        "accumulated_knowledge": {
            "success_patterns": knowledge.get("success_patterns", [])[:5] if knowledge else [],
            "anti_patterns": knowledge.get("anti_patterns", [])[:5] if knowledge else [],
            "domain_insights": knowledge.get("domain_knowledge", [])[:5] if knowledge else []
        },
        "conversation_summary": {
            "user_intent": state.get("task_objective", ""),
            "user_preferences": [],
            "key_exchanges": []
        }
    }
    
    return transfer_doc


def handle_succession(gas_dir: Path, current_gen: int, 
                      agent_id: Optional[str] = None) -> Dict:
    """
    Handle succession from current generation to next.
    Returns info about the new generation.
    """
    log(f"Handling succession from generation {current_gen} to {current_gen + 1}")
    
    # Create transfer document
    transfer_doc = create_transfer_document(gas_dir, current_gen, agent_id)
    
    # Spawn new generation
    new_gen_info = spawn_generation(
        gas_dir=gas_dir,
        generation=current_gen + 1,
        agent_id=agent_id,
        transfer_doc=transfer_doc
    )
    
    # Update old generation status
    if agent_id:
        old_status_path = gas_dir / "agents" / agent_id / "generations" / f"gen-{current_gen}" / "status.json"
    else:
        old_status_path = gas_dir / "generations" / f"gen-{current_gen}" / "status.json"
    
    old_status = read_json(old_status_path) or {}
    old_status["status"] = "succeeded"
    old_status["succeeded_to"] = current_gen + 1
    old_status["completed_at"] = timestamp()
    write_json(old_status_path, old_status)
    
    # Consolidate learnings to knowledge store
    consolidate_learnings(gas_dir, current_gen, agent_id)
    
    return new_gen_info


def consolidate_learnings(gas_dir: Path, generation: int, 
                          agent_id: Optional[str] = None):
    """Consolidate learnings from a generation into the knowledge store."""
    status = read_generation_status(gas_dir, generation, agent_id)
    knowledge = read_json(gas_dir / "knowledge" / "store.json")
    
    if not status or not knowledge:
        return
    
    learnings = status.get("learnings", [])
    
    for learning in learnings:
        learning_type = learning.get("type", "insight")
        learning["source_generation"] = generation
        learning["source_agent"] = agent_id
        learning["added_at"] = timestamp()
        
        if learning_type == "success_pattern":
            knowledge["success_patterns"].append(learning)
        elif learning_type == "anti_pattern":
            knowledge["anti_patterns"].append(learning)
        else:
            knowledge["domain_knowledge"].append(learning)
    
    knowledge["last_updated"] = timestamp()
    knowledge["generations_completed"] = knowledge.get("generations_completed", 0) + 1
    
    write_json(gas_dir / "knowledge" / "store.json", knowledge)
    log(f"Consolidated {len(learnings)} learnings from generation {generation}")


# =============================================================================
# Run Loop
# =============================================================================

def run_orchestrator(gas_dir: Path, mode: str = "single"):
    """Main run loop for the orchestrator."""
    log(f"Starting GAS orchestrator for: {gas_dir}")
    log(f"Mode: {mode}")
    
    state = read_json(gas_dir / "gas-state.json")
    if not state:
        raise RuntimeError(f"Cannot read GAS state from {gas_dir}")
    
    # Spawn first generation if not exists
    current_gen = state.get("current_generation", 0)
    if current_gen == 0:
        spawn_generation(gas_dir, 1)
        current_gen = 1
    
    running = True
    
    def signal_handler(sig, frame):
        nonlocal running
        log("Received shutdown signal, stopping...")
        running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    while running:
        try:
            gen_status = monitor_generation(gas_dir, current_gen)
            
            if gen_status == "completed":
                log(f"Generation {current_gen} completed successfully!")
                consolidate_learnings(gas_dir, current_gen)
                
                # Check if task is complete
                status = read_generation_status(gas_dir, current_gen)
                if status and status.get("task_complete", False):
                    log("Task marked as complete. Generating final report.")
                    generate_report(gas_dir)
                    running = False
                else:
                    # Task not complete, spawn next generation
                    new_gen_info = handle_succession(gas_dir, current_gen)
                    current_gen = new_gen_info["generation"]
            
            elif gen_status == "needs_succession":
                new_gen_info = handle_succession(gas_dir, current_gen)
                current_gen = new_gen_info["generation"]
            
            elif gen_status == "failed":
                log(f"Generation {current_gen} failed!", "ERROR")
                # Could implement retry logic here
                running = False
            
            else:
                # Still running, wait and check again
                time.sleep(DEFAULT_CONFIG["poll_interval_seconds"])
                
        except Exception as e:
            log(f"Error in orchestrator loop: {e}", "ERROR")
            time.sleep(5)
    
    log("Orchestrator stopped")


# =============================================================================
# Reporting
# =============================================================================

def generate_report(gas_dir: Path) -> str:
    """Generate final GAS report."""
    state = read_json(gas_dir / "gas-state.json")
    knowledge = read_json(gas_dir / "knowledge" / "store.json")
    
    if not state:
        return "Error: Cannot read GAS state"
    
    # Calculate duration
    start_time = datetime.fromisoformat(state.get("start_time", "").replace("Z", "+00:00"))
    duration = datetime.utcnow().replace(tzinfo=start_time.tzinfo) - start_time
    duration_str = str(duration).split('.')[0]  # Remove microseconds
    
    report = f"""
================================================================================
                        GAS TASK COMPLETION REPORT
================================================================================

Project: {state.get('project_name', 'Unknown')}
Mode: {state.get('mode', 'single')}
Started: {state.get('start_time', 'Unknown')}
Duration: {duration_str}

--------------------------------------------------------------------------------
GENERATIONS SUMMARY
--------------------------------------------------------------------------------
Total Generations: {state.get('total_generations', 0)}
Final Generation: {state.get('current_generation', 0)}

--------------------------------------------------------------------------------
KNOWLEDGE ACCUMULATED
--------------------------------------------------------------------------------
Success Patterns: {len(knowledge.get('success_patterns', [])) if knowledge else 0}
Anti-Patterns: {len(knowledge.get('anti_patterns', [])) if knowledge else 0}
Domain Insights: {len(knowledge.get('domain_knowledge', [])) if knowledge else 0}

--------------------------------------------------------------------------------
OUTPUT LOCATION
--------------------------------------------------------------------------------
All deliverables: {gas_dir}/output/
Knowledge store: {gas_dir}/knowledge/store.json

================================================================================
"""
    
    # Write report to file
    report_path = gas_dir / "FINAL_REPORT.md"
    with open(report_path, 'w') as f:
        f.write(report)
    
    log(f"Final report written to: {report_path}")
    print(report)
    return report


def get_status(gas_dir: Path) -> str:
    """Get current status of GAS workspace."""
    state = read_json(gas_dir / "gas-state.json")
    if not state:
        return "Error: Cannot read GAS state"
    
    current_gen = state.get("current_generation", 0)
    gen_status = None
    
    if current_gen > 0:
        gen_status = read_generation_status(gas_dir, current_gen)
    
    # Calculate display values
    progress_pct = f"{gen_status.get('progress', 0) * 100:.1f}%" if gen_status else "N/A"
    confidence_val = gen_status.get('confidence', 0) if gen_status else "N/A"
    interactions_val = gen_status.get('interactions', 0) if gen_status else 0
    errors_val = gen_status.get('errors', 0) if gen_status else 0
    status_val = gen_status.get('status', 'unknown') if gen_status else 'N/A'
    
    status = f"""
================================================================================
                           GAS STATUS
================================================================================

Project: {state.get('project_name', 'Unknown')}
Mode: {state.get('mode', 'single')}
Status: {state.get('status', 'unknown')}

Current Generation: {current_gen}
Total Generations: {state.get('total_generations', 0)}

Generation Status:
  - Status: {status_val}
  - Progress: {progress_pct}
  - Confidence: {confidence_val}
  - Interactions: {interactions_val}
  - Errors: {errors_val}

Workspace: {gas_dir}
================================================================================
"""
    print(status)
    return status


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="GAS Orchestrator - Generational Agent Succession",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize a new workspace
  python3 gas-orchestrator.py init "My Project" "Build a REST API"
  
  # Run the orchestrator
  python3 gas-orchestrator.py run /workspace/my-project-gas
  
  # Check status
  python3 gas-orchestrator.py status /workspace/my-project-gas
  
  # Manually spawn a generation
  python3 gas-orchestrator.py spawn /workspace/my-project-gas --generation=2
  
  # Generate report
  python3 gas-orchestrator.py report /workspace/my-project-gas
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # init command
    init_parser = subparsers.add_parser("init", help="Initialize a new GAS workspace")
    init_parser.add_argument("project_name", help="Name of the project")
    init_parser.add_argument("task_objective", help="Main objective of the task")
    init_parser.add_argument("--mode", choices=["single", "swarm"], default="single",
                            help="Execution mode (default: single)")
    
    # run command
    run_parser = subparsers.add_parser("run", help="Run the orchestrator")
    run_parser.add_argument("gas_dir", help="Path to GAS workspace")
    run_parser.add_argument("--mode", choices=["single", "swarm"], default=None,
                           help="Override execution mode")
    
    # status command
    status_parser = subparsers.add_parser("status", help="Get current status")
    status_parser.add_argument("gas_dir", help="Path to GAS workspace")
    
    # spawn command
    spawn_parser = subparsers.add_parser("spawn", help="Spawn a new generation")
    spawn_parser.add_argument("gas_dir", help="Path to GAS workspace")
    spawn_parser.add_argument("--generation", type=int, help="Generation number to spawn")
    spawn_parser.add_argument("--agent", help="Agent ID (for swarm mode)")
    
    # report command
    report_parser = subparsers.add_parser("report", help="Generate final report")
    report_parser.add_argument("gas_dir", help="Path to GAS workspace")
    
    args = parser.parse_args()
    
    if args.command == "init":
        gas_dir = init_workspace(args.project_name, args.task_objective, args.mode)
        print(f"\nWorkspace initialized: {gas_dir}")
        print(f"\nNext steps:")
        print(f"  1. Start dashboard: python3 {RESOURCES_DIR}/gas-dashboard-server.py")
        print(f"  2. Run orchestrator: python3 {SCRIPT_DIR}/gas-orchestrator.py run {gas_dir}")
        
    elif args.command == "run":
        gas_dir = Path(args.gas_dir)
        state = read_json(gas_dir / "gas-state.json")
        mode = args.mode or (state.get("mode", "single") if state else "single")
        run_orchestrator(gas_dir, mode)
        
    elif args.command == "status":
        get_status(Path(args.gas_dir))
        
    elif args.command == "spawn":
        gas_dir = Path(args.gas_dir)
        generation = args.generation or (get_current_generation(gas_dir) + 1)
        result = spawn_generation(gas_dir, generation, args.agent)
        print(f"Spawned: {json.dumps(result, indent=2)}")
        
    elif args.command == "report":
        generate_report(Path(args.gas_dir))
        
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
