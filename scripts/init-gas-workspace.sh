#!/bin/bash
# Initialize GAS Workspace
# Usage: ./init-gas-workspace.sh <project-name> <task-objective>

set -e

PROJECT_NAME="${1:-my-project}"
TASK_OBJECTIVE="${2:-Complete the assigned task}"
PROJECT_SLUG=$(echo "$PROJECT_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')

WORKSPACE_BASE="${WORKSPACE_BASE:-/workspace}"
GAS_DIR="${WORKSPACE_BASE}/${PROJECT_SLUG}-gas"

echo "=========================================="
echo "Initializing GAS Workspace"
echo "=========================================="
echo "Project: $PROJECT_NAME"
echo "Slug: $PROJECT_SLUG"
echo "Directory: $GAS_DIR"
echo "=========================================="

# Create directory structure
mkdir -p "$GAS_DIR"/{generations,knowledge,output,shared}

# Initialize GAS state
cat > "$GAS_DIR/gas-state.json" << EOF
{
  "project_name": "$PROJECT_NAME",
  "project_slug": "$PROJECT_SLUG",
  "start_time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "current_generation": 1,
  "total_generations": 0,
  "task_objective": "$TASK_OBJECTIVE",
  "subtasks": [],
  "status": "initialized",
  "knowledge_store": "knowledge/store.json"
}
EOF

# Initialize empty knowledge store
cat > "$GAS_DIR/knowledge/store.json" << EOF
{
  "project": "$PROJECT_SLUG",
  "created": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "last_updated": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "generations_completed": 0,
  "success_patterns": [],
  "anti_patterns": [],
  "domain_knowledge": []
}
EOF

# Create first generation directory
mkdir -p "$GAS_DIR/generations/gen-1"

# Initialize first generation status
cat > "$GAS_DIR/generations/gen-1/status.json" << EOF
{
  "generation": 1,
  "status": "pending",
  "started_at": null,
  "interactions": 0,
  "progress": 0,
  "current_task": "Waiting to start",
  "completed_tasks": [],
  "confidence": 1.0,
  "errors": 0,
  "learnings": []
}
EOF

echo ""
echo "GAS workspace initialized at: $GAS_DIR"
echo ""
echo "Directory structure:"
find "$GAS_DIR" -type f | head -20
echo ""
echo "Next steps:"
echo "1. Launch GAS dashboard: python3 gas-dashboard-server.py"
echo "2. Export port: /app/export-port.sh 8080"
echo "3. Start Generation 1 agent"
