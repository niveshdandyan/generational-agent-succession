# Generational Agent Succession (GAS)

> "Fresh context, inherited wisdom. Every generation improves."

A Claude Code skill for maintaining agent quality over long-running tasks through controlled succession between agent generations.

## The Problem

Long-running AI agents suffer from:
- **Context Pollution**: Accumulated noise dilutes useful signal
- **Attention Drift**: Models lose focus on original objectives
- **Error Accumulation**: Small mistakes compound over time
- **Memory Overflow**: Context windows fill with low-value data

Research shows effective context degrades after ~1000 tokens of noise, and "Lost in the Middle" phenomenon causes 20-40% performance drops.

## The Solution

GAS implements a biologically-inspired succession cycle:

```
┌─────────────────────────────────────────────────────────────┐
│  Task Start → Gen 1 → [Degrade?] → Compress → Gen 2 → ...  │
│                  ↑                              │            │
│                  └── Fresh Context + Wisdom ───┘            │
└─────────────────────────────────────────────────────────────┘
```

When degradation triggers fire:
1. Current generation compresses its knowledge
2. New generation spawns with fresh context
3. Knowledge transfers via structured document
4. Patterns that worked are reinforced
5. Anti-patterns are recorded to avoid

## Installation

```bash
# Copy to Claude skills directory
cp -r generational-agent-succession ~/.claude/skills/
```

## Usage

### Trigger the skill:
```
/gas Build me a full-stack e-commerce platform with auth, payments, and admin dashboard
```

### Or use trigger phrases:
- "gas build [task]"
- "long running task: [task]"
- "marathon task: [task]"

## How It Works

### 1. Task Initialization
- Parse task into subtasks
- Initialize workspace and knowledge store
- Launch monitoring dashboard

### 2. Generation Execution
- Each generation works on assigned subtasks
- Self-monitors for degradation signals
- Records learnings as it works

### 3. Degradation Detection
Triggers evaluated continuously:

| Trigger | Threshold | Weight |
|---------|-----------|--------|
| Interactions | 150 | 0.25 |
| Confidence | < 0.70 | 0.30 |
| Error Rate | > 15% | 0.25 |
| Stall Time | > 10 min | 0.20 |

Succession when composite score > 0.70

### 4. Knowledge Transfer
Parent creates transfer document:
- Task state (critical - always transfer)
- Working memory (important - compress)
- Accumulated patterns (context - selective)

Target: 15% compression, max 3000 tokens

### 5. Succession Handoff
1. Parent completes atomic operations
2. Parent generates transfer document
3. Child spawns with fresh context
4. Transfer document injected as initial context
5. Parent terminates

## File Structure

```
generational-agent-succession/
├── SKILL.md                    # Main skill definition
├── README.md                   # This file
├── resources/
│   ├── gas-config.yaml         # Configuration options
│   └── gas-dashboard-server.py # Real-time monitoring
├── templates/
│   ├── generation-prompt.md    # Agent prompt template
│   └── transfer-document.yaml  # Transfer doc template
├── scripts/
│   ├── init-gas-workspace.sh   # Initialize workspace
│   ├── spawn-generation.sh     # Spawn new generation
│   └── check-triggers.py       # Evaluate triggers
└── examples/
    └── basic-usage.md          # Usage example
```

## Configuration

See `resources/gas-config.yaml`:

```yaml
triggers:
  interaction_limit: 150
  confidence_threshold: 0.70
  error_rate_threshold: 0.15

transfer:
  max_tokens: 3000
  compression_ratio: 0.15

safety:
  max_generations: 20
  max_total_duration_hours: 4
```

## Dashboard

Real-time monitoring at `http://localhost:8080/` shows:
- Current generation progress
- Generation timeline
- Accumulated knowledge count
- Trigger status

## Expected Benefits

| Metric | Without GAS | With GAS |
|--------|-------------|----------|
| Context Efficiency | ~30% | ~85% |
| Error Rate | ~15% | ~5% |
| Task Completion | ~80% | ~95% |

## Integration with Agent Architect

GAS can wrap Agent Architect swarms:

```
Agent Architect spawns parallel swarm
    │
    ├── Agent 1 → GAS Gen 1 → Gen 2 → Gen 3
    ├── Agent 2 → GAS Gen 1 → Gen 2
    └── Agent 3 → GAS Gen 1
```

Each parallel agent can have its own generational succession.

## Research Background

Based on research into:
- Context window degradation (Liu et al., "Lost in the Middle")
- Memory consolidation (MemGPT, Packer et al.)
- Knowledge distillation (Hinton et al.)
- Cognitive architectures (ACT-R, SOAR)
- Biological sleep consolidation

See `/outputs/RESEARCH-SUMMARY.md` for full literature review.

## License

MIT

---

*"Each generation stands on the shoulders of the last. Context fades, wisdom remains."*
