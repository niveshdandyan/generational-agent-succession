# GAS Basic Usage Example

This example shows how to use Generational Agent Succession for a multi-phase project.

## Scenario: Building a Task Management API

User request: "Build me a REST API for task management with user authentication"

---

## Step 1: Initialize GAS Workspace

```bash
# The orchestrator initializes the workspace
./scripts/init-gas-workspace.sh "Task Manager API" "Build REST API with auth"

# Output:
# GAS workspace initialized at: /workspace/task-manager-api-gas
```

## Step 2: Launch Dashboard

```bash
# Start the monitoring dashboard
export GAS_DIR=/workspace/task-manager-api-gas
export GAS_NAME="Task Manager API"
python3 resources/gas-dashboard-server.py 8080 &

# Export for user access
/app/export-port.sh 8080
```

## Step 3: Spawn Generation 1

The orchestrator launches Generation 1 using the Task tool:

```markdown
**Task Description**: Generation 1: Task Manager API

**Prompt**: [Contents of templates/generation-prompt.md with variables filled in]

**Agent Type**: general-purpose

**Run in Background**: true
```

## Step 4: Generation 1 Works

Generation 1 works on:
- Project setup (package.json, tsconfig.json)
- Database schema design
- Basic Express server setup

After ~100 interactions, Generation 1 notices confidence dropping:

```json
{
  "generation": 1,
  "status": "running",
  "interactions": 102,
  "progress": 0.35,
  "confidence": 0.65,
  "current_task": "Setting up authentication middleware",
  "completed_tasks": ["Project setup", "Database schema", "Express server"],
  "errors": 2,
  "learnings": [
    {
      "type": "success_pattern",
      "context": "Express middleware",
      "content": "Use async error handler wrapper for all routes"
    }
  ]
}
```

## Step 5: Trigger Evaluation

The orchestrator runs trigger evaluation:

```bash
python3 scripts/check-triggers.py /workspace/task-manager-api-gas 1

# Output:
# Weighted Score: 0.58
# Should Handoff: True
# Urgency: soon
# Primary Trigger: confidence
```

## Step 6: Generation 1 Creates Transfer Document

Generation 1 prepares `transfer.json`:

```yaml
meta:
  parent_generation: 1
  child_generation: 2
  reason: "confidence_decay"

task_state:
  objective: "Build REST API with auth"
  overall_progress: 0.35
  current_phase: "Authentication"
  remaining_phases:
    - "User CRUD endpoints"
    - "Task CRUD endpoints"
    - "Testing"
    - "Documentation"

completed_work:
  subtasks:
    - name: "Project setup"
      files: ["package.json", "tsconfig.json", ".env.example"]
    - name: "Database schema"
      files: ["src/db/schema.sql", "src/models/"]
    - name: "Express server"
      files: ["src/index.ts", "src/routes/"]

  key_decisions:
    - decision: "Using bcrypt for password hashing"
      reason: "Industry standard, well-tested"
    - decision: "JWT with 1-hour expiry"
      reason: "Good balance of security and UX"

working_memory:
  active_files:
    - path: "src/middleware/auth.ts"
      status: "in_progress"
      notes: "Token verification done, need refresh logic"

  next_steps:
    - "Implement refresh token rotation"
    - "Add user registration endpoint"
    - "Add login endpoint"

accumulated_knowledge:
  success_patterns:
    - context: "Express routes"
      pattern: "Wrap async handlers with error catcher"
```

## Step 7: Spawn Generation 2

The orchestrator spawns Generation 2 with the transfer document injected:

```markdown
# Generation 2 Worker

You are Generation 2 of GAS working on: Task Manager API

## Inherited Knowledge

[Transfer document from Generation 1]

## Success Patterns (inherited)

- Express routes: Wrap async handlers with error catcher

## Your Tasks

1. Implement refresh token rotation
2. Add user registration endpoint
3. Add login endpoint
4. User CRUD endpoints
5. Task CRUD endpoints
...
```

## Step 8: Generation 2 Continues

Generation 2 starts with:
- Fresh context window
- Inherited knowledge from Generation 1
- Clear understanding of completed work

After another 120 interactions, Generation 2 completes auth and moves to CRUD endpoints.

## Step 9: Final Generation Completes

Generation 3 finishes the remaining work:
- Testing
- Documentation
- Final cleanup

Final status:

```json
{
  "generation": 3,
  "status": "completed",
  "final_progress": 1.0,
  "task_complete": true,
  "files_created": ["src/**/*.ts", "tests/**/*.test.ts", "README.md"],
  "learnings": [...]
}
```

## Final Output

```
========================================
GAS Task Complete: Task Manager API
========================================

Total Generations: 3
Total Duration: 1h 45m
Files Created: 34
Success Patterns: 8
Anti-Patterns: 3

Generations Timeline:
| Gen | Duration | Work Done          | Succession Reason  |
|-----|----------|--------------------|--------------------|
| 1   | 35 min   | Setup, DB, Server  | confidence_decay   |
| 2   | 45 min   | Auth, User CRUD    | interaction_limit  |
| 3   | 25 min   | Task CRUD, Tests   | task_complete      |

Output: /workspace/task-manager-api-gas/output/
========================================
```

---

## Key Benefits Demonstrated

1. **Fresh Context**: Each generation started clean, avoiding context pollution
2. **Knowledge Transfer**: Learnings passed between generations
3. **Self-Monitoring**: Agents detected their own degradation
4. **Continuous Quality**: No degradation in output quality despite long task
5. **Accumulated Wisdom**: Success patterns improved each generation
