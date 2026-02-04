#!/usr/bin/env python3
"""
GAS Prompt Renderer
===================
Renders generation-prompt.md templates with actual values.

Usage:
    python3 render-prompt.py --template <path> --generation <N> --project <name> --objective <obj>
    python3 render-prompt.py --gas-dir <path> --generation <N> [--agent <agent-id>]
"""

import os
import sys
import json
import argparse
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any


# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATES_DIR = SKILL_DIR / "templates"


# =============================================================================
# Utility Functions
# =============================================================================

def timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: Path) -> Optional[Dict]:
    """Read JSON file safely."""
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def slugify(name: str) -> str:
    """Convert project name to slug."""
    return name.lower().replace(' ', '-').replace('_', '-')


# =============================================================================
# Template Engine (Simplified Handlebars-like)
# =============================================================================

class TemplateRenderer:
    """
    Simple template renderer supporting:
    - {{VARIABLE}} - Variable substitution
    - {{#if CONDITION}}...{{else}}...{{/if}} - Conditionals
    - {{#each ARRAY}}...{{/each}} - Loops
    - {{#unless CONDITION}}...{{/unless}} - Inverse conditionals
    """
    
    def __init__(self, template: str, variables: Dict[str, Any]):
        self.template = template
        self.variables = variables
    
    def render(self) -> str:
        """Render the template with variables."""
        result = self.template
        
        # Handle conditionals first
        result = self._process_conditionals(result)
        
        # Handle loops
        result = self._process_loops(result)
        
        # Handle simple variable substitution
        result = self._substitute_variables(result)
        
        # Clean up any remaining template syntax
        result = self._cleanup(result)
        
        return result
    
    def _substitute_variables(self, text: str) -> str:
        """Replace {{VARIABLE}} with values."""
        for key, value in self.variables.items():
            placeholder = "{{" + key + "}}"
            if isinstance(value, (list, dict)):
                replacement = json.dumps(value, indent=2)
            elif isinstance(value, bool):
                replacement = str(value).lower()
            else:
                replacement = str(value) if value is not None else ""
            text = text.replace(placeholder, replacement)
        return text
    
    def _process_conditionals(self, text: str) -> str:
        """Process {{#if}}, {{else}}, {{/if}} blocks."""
        # Pattern for if/else/endif blocks
        pattern = r'\{\{#if\s+(\w+)\}\}(.*?)(?:\{\{else\}\}(.*?))?\{\{/if\}\}'
        
        def replace_if(match):
            condition_var = match.group(1)
            if_content = match.group(2) or ""
            else_content = match.group(3) or ""
            
            # Check condition
            condition_value = self.variables.get(condition_var, False)
            if isinstance(condition_value, str):
                condition_value = condition_value.lower() == "true"
            
            return if_content if condition_value else else_content
        
        # Process recursively (for nested ifs)
        max_iterations = 10
        for _ in range(max_iterations):
            new_text = re.sub(pattern, replace_if, text, flags=re.DOTALL)
            if new_text == text:
                break
            text = new_text
        
        # Handle {{#unless}} (inverse of if)
        pattern = r'\{\{#unless\s+(\w+)\}\}(.*?)\{\{/unless\}\}'
        
        def replace_unless(match):
            condition_var = match.group(1)
            content = match.group(2) or ""
            
            condition_value = self.variables.get(condition_var, False)
            if isinstance(condition_value, str):
                condition_value = condition_value.lower() == "true"
            
            return "" if condition_value else content
        
        text = re.sub(pattern, replace_unless, text, flags=re.DOTALL)
        
        return text
    
    def _process_loops(self, text: str) -> str:
        """Process {{#each ARRAY}}...{{/each}} blocks."""
        pattern = r'\{\{#each\s+(\w+)\}\}(.*?)\{\{/each\}\}'
        
        def replace_each(match):
            array_var = match.group(1)
            item_template = match.group(2)
            
            array_value = self.variables.get(array_var, [])
            if not isinstance(array_value, list):
                return ""
            
            results = []
            for index, item in enumerate(array_value):
                item_text = item_template
                # Replace {{this}} or {{this.property}}
                if isinstance(item, dict):
                    for key, value in item.items():
                        item_text = item_text.replace("{{this." + key + "}}", str(value))
                    item_text = item_text.replace("{{this}}", json.dumps(item))
                else:
                    item_text = item_text.replace("{{this}}", str(item))
                item_text = item_text.replace("{{@index}}", str(index + 1))
                results.append(item_text)
            
            return "\n".join(results)
        
        return re.sub(pattern, replace_each, text, flags=re.DOTALL)
    
    def _cleanup(self, text: str) -> str:
        """Clean up any remaining template markers."""
        # Remove any remaining {{ }} blocks
        text = re.sub(r'\{\{[^}]+\}\}', '', text)
        # Remove HTML comments we added
        text = re.sub(r'<!-- \w+ removed -->', '', text)
        # Clean up extra blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


# =============================================================================
# Prompt Building
# =============================================================================

def build_variables_from_gas_dir(gas_dir: Path, generation: int,
                                  agent_id: Optional[str] = None) -> Dict[str, Any]:
    """Build template variables from GAS workspace state."""
    state = read_json(gas_dir / "gas-state.json")
    knowledge = read_json(gas_dir / "knowledge" / "store.json")
    
    if not state:
        raise RuntimeError(f"Cannot read GAS state from {gas_dir}")
    
    # Determine paths
    if agent_id:
        gen_dir = gas_dir / "agents" / agent_id / "generations" / f"gen-{generation}"
        parent_dir = gas_dir / "agents" / agent_id / "generations" / f"gen-{generation-1}"
    else:
        gen_dir = gas_dir / "generations" / f"gen-{generation}"
        parent_dir = gas_dir / "generations" / f"gen-{generation-1}"
    
    # Load transfer document from parent
    transfer_doc = None
    if generation > 1 and (parent_dir / "transfer.json").exists():
        transfer_doc = read_json(parent_dir / "transfer.json")
    
    # Get subtasks from state or transfer doc
    remaining_subtasks = []
    current_subtask = state.get("task_objective", "Complete the assigned task")
    
    if transfer_doc:
        remaining_subtasks = transfer_doc.get("task_state", {}).get("remaining_phases", [])
        if remaining_subtasks:
            current_subtask = remaining_subtasks[0] if isinstance(remaining_subtasks[0], str) else remaining_subtasks[0].get("name", current_subtask)
    
    variables = {
        "GENERATION": generation,
        "NEXT_GENERATION": generation + 1,
        "PARENT_GENERATION": generation - 1 if generation > 1 else 0,
        "PROJECT_NAME": state.get("project_name", "Project"),
        "PROJECT_SLUG": state.get("project_slug", slugify(state.get("project_name", "project"))),
        "TASK_OBJECTIVE": state.get("task_objective", "Complete the assigned task"),
        "TIMESTAMP": timestamp(),
        "IS_FIRST_GENERATION": generation == 1,
        "WORKSPACE": str(gas_dir),
        "CURRENT_SUBTASK": current_subtask,
        "REMAINING_SUBTASKS": [
            {"name": s if isinstance(s, str) else s.get("name", "Task"),
             "status": "pending" if isinstance(s, str) else s.get("status", "pending"),
             "priority": "normal" if isinstance(s, str) else s.get("priority", "normal")}
            for s in remaining_subtasks
        ],
        "TRANSFER_DOCUMENT": json.dumps(transfer_doc, indent=2) if transfer_doc else "",
        "INITIAL_CONTEXT": state.get("task_objective", "") if generation == 1 else "",
        "SUCCESS_PATTERNS": knowledge.get("success_patterns", [])[:5] if knowledge else [],
        "ANTI_PATTERNS": knowledge.get("anti_patterns", [])[:5] if knowledge else [],
        "AGENT_ID": agent_id or "",
        "AGENT_NUMBER": agent_id.split("-")[1] if agent_id and "-" in agent_id else "1"
    }
    
    return variables


def render_prompt(template_path: Path, variables: Dict[str, Any]) -> str:
    """Render a template file with variables."""
    with open(template_path, 'r') as f:
        template = f.read()
    
    renderer = TemplateRenderer(template, variables)
    return renderer.render()


def render_from_gas_dir(gas_dir: Path, generation: int,
                        agent_id: Optional[str] = None,
                        template_path: Optional[Path] = None) -> str:
    """Render a generation prompt from GAS workspace state."""
    if template_path is None:
        template_path = TEMPLATES_DIR / "generation-prompt.md"
    
    variables = build_variables_from_gas_dir(gas_dir, generation, agent_id)
    return render_prompt(template_path, variables)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="GAS Prompt Renderer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Render prompt from GAS workspace
  python3 render-prompt.py --gas-dir /workspace/my-project-gas --generation 1
  
  # Render with custom template
  python3 render-prompt.py --template ./my-template.md --generation 1 \\
    --project "My Project" --objective "Build an API"
  
  # Save to file
  python3 render-prompt.py --gas-dir /workspace/project-gas --generation 2 \\
    --output /tmp/gen2-prompt.md
"""
    )
    
    parser.add_argument("--gas-dir", type=Path, help="Path to GAS workspace")
    parser.add_argument("--template", type=Path, help="Path to template file")
    parser.add_argument("--generation", type=int, required=True, help="Generation number")
    parser.add_argument("--agent", help="Agent ID (for swarm mode)")
    parser.add_argument("--project", help="Project name (if not using --gas-dir)")
    parser.add_argument("--objective", help="Task objective (if not using --gas-dir)")
    parser.add_argument("--output", type=Path, help="Output file path (default: stdout)")
    
    args = parser.parse_args()
    
    if args.gas_dir:
        # Render from GAS workspace
        rendered = render_from_gas_dir(
            gas_dir=args.gas_dir,
            generation=args.generation,
            agent_id=args.agent,
            template_path=args.template
        )
    elif args.template and args.project and args.objective:
        # Render with manual variables
        variables = {
            "GENERATION": args.generation,
            "NEXT_GENERATION": args.generation + 1,
            "PARENT_GENERATION": args.generation - 1,
            "PROJECT_NAME": args.project,
            "PROJECT_SLUG": slugify(args.project),
            "TASK_OBJECTIVE": args.objective,
            "TIMESTAMP": timestamp(),
            "IS_FIRST_GENERATION": args.generation == 1,
            "CURRENT_SUBTASK": args.objective,
            "REMAINING_SUBTASKS": [],
            "TRANSFER_DOCUMENT": "",
            "INITIAL_CONTEXT": args.objective if args.generation == 1 else "",
            "SUCCESS_PATTERNS": [],
            "ANTI_PATTERNS": []
        }
        rendered = render_prompt(args.template, variables)
    else:
        parser.error("Either --gas-dir or (--template, --project, --objective) are required")
        return
    
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w') as f:
            f.write(rendered)
        print(f"Prompt written to: {args.output}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
