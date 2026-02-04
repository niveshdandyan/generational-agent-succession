#!/bin/bash
# Spawn a new GAS generation
# Usage: ./spawn-generation.sh <gas-dir> <generation-number>

set -e

GAS_DIR="${1:-.}"
GEN_NUM="${2:-1}"

GEN_DIR="$GAS_DIR/generations/gen-$GEN_NUM"

echo "=========================================="
echo "Spawning Generation $GEN_NUM"
echo "=========================================="

# Create generation directory
mkdir -p "$GEN_DIR"

# Initialize status
cat > "$GEN_DIR/status.json" << EOF
{
  "generation": $GEN_NUM,
  "status": "running",
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "interactions": 0,
  "progress": 0,
  "current_task": "Initializing...",
  "completed_tasks": [],
  "confidence": 1.0,
  "errors": 0,
  "learnings": []
}
EOF

# Update gas-state.json
if [ -f "$GAS_DIR/gas-state.json" ]; then
    # Use Python for JSON manipulation (more reliable than jq)
    python3 << PYEOF
import json
with open("$GAS_DIR/gas-state.json", 'r') as f:
    state = json.load(f)
state['current_generation'] = $GEN_NUM
state['total_generations'] = max(state.get('total_generations', 0), $GEN_NUM)
with open("$GAS_DIR/gas-state.json", 'w') as f:
    json.dump(state, f, indent=2)
PYEOF
fi

echo "Generation $GEN_NUM initialized at: $GEN_DIR"
echo "Status file: $GEN_DIR/status.json"
