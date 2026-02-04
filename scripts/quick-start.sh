#!/bin/bash
# =============================================================================
# GAS Quick Start Script
# =============================================================================
# One-command setup for Generational Agent Succession
#
# Usage:
#   ./quick-start.sh "Project Name" "Task objective description"
#
# Example:
#   ./quick-start.sh "Todo API" "Build a REST API for task management with auth"
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SKILL_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Parse arguments
PROJECT_NAME="${1:-My Project}"
TASK_OBJECTIVE="${2:-Complete the assigned task}"
MODE="${3:-single}"

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                    GAS Quick Start - v2.0.1                              ║"
echo "║           Generational Agent Succession Made Easy                         ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${BLUE}Project:${NC} $PROJECT_NAME"
echo -e "${BLUE}Task:${NC} $TASK_OBJECTIVE"
echo -e "${BLUE}Mode:${NC} $MODE"
echo ""

# Step 1: Initialize workspace
echo -e "${YELLOW}[1/4]${NC} Initializing GAS workspace..."
OUTPUT=$(python3 "$SCRIPT_DIR/gas-orchestrator.py" init "$PROJECT_NAME" "$TASK_OBJECTIVE" --mode="$MODE" 2>&1)

# Extract the workspace path from output
GAS_DIR=$(echo "$OUTPUT" | grep -o '/[^ ]*-gas' | head -1)

if [ -z "$GAS_DIR" ]; then
    echo -e "${RED}Error: Failed to initialize workspace${NC}"
    echo "$OUTPUT"
    exit 1
fi

echo -e "${GREEN}✓${NC} Workspace created: $GAS_DIR"

# Step 2: Spawn first generation
echo -e "${YELLOW}[2/4]${NC} Spawning Generation 1..."
python3 "$SCRIPT_DIR/gas-orchestrator.py" spawn "$GAS_DIR" --generation=1 > /dev/null 2>&1
echo -e "${GREEN}✓${NC} Generation 1 initialized"

# Step 3: Render first prompt
echo -e "${YELLOW}[3/4]${NC} Rendering generation prompt..."
PROMPT_FILE="$GAS_DIR/generations/gen-1/prompt.md"
python3 "$SCRIPT_DIR/render-prompt.py" --gas-dir "$GAS_DIR" --generation 1 --output "$PROMPT_FILE"
echo -e "${GREEN}✓${NC} Prompt saved: $PROMPT_FILE"

# Step 4: Start dashboard (optional)
echo -e "${YELLOW}[4/4]${NC} Dashboard setup..."

DASHBOARD_STANDALONE="$SKILL_DIR/resources/gas-dashboard-server-standalone.py"
DASHBOARD_MODULAR="$SKILL_DIR/resources/dashboard/server/main.py"

if [ -f "$DASHBOARD_STANDALONE" ]; then
    DASHBOARD_SCRIPT="$DASHBOARD_STANDALONE"
elif [ -f "$DASHBOARD_MODULAR" ]; then
    DASHBOARD_SCRIPT="$DASHBOARD_MODULAR"
else
    DASHBOARD_SCRIPT=""
fi

echo ""
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                          ✓ GAS READY!                                     ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${CYAN}Workspace:${NC} $GAS_DIR"
echo ""
echo -e "${CYAN}Files Created:${NC}"
echo "  ├── gas-state.json        (main state file)"
echo "  ├── knowledge/store.json  (shared knowledge)"
echo "  └── generations/gen-1/"
echo "      ├── status.json       (generation status)"
echo "      └── prompt.md         (agent prompt)"
echo ""

echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "  1. Start the dashboard (in a separate terminal):"
if [ -n "$DASHBOARD_SCRIPT" ]; then
    echo -e "     ${GREEN}export GAS_DIR=$GAS_DIR && python3 $DASHBOARD_SCRIPT${NC}"
else
    echo "     (Dashboard script not found - copy from resources/)"
fi
echo ""
echo "  2. Copy the generation prompt and start working:"
echo -e "     ${GREEN}cat $PROMPT_FILE${NC}"
echo ""
echo "  3. Monitor triggers periodically:"
echo -e "     ${GREEN}python3 $SCRIPT_DIR/check-triggers.py $GAS_DIR 1${NC}"
echo ""
echo "  4. When ready for succession, create transfer document and run:"
echo -e "     ${GREEN}python3 $SCRIPT_DIR/gas-orchestrator.py spawn $GAS_DIR --generation=2${NC}"
echo ""
echo "  5. Or run the full orchestrator loop:"
echo -e "     ${GREEN}python3 $SCRIPT_DIR/gas-orchestrator.py run $GAS_DIR${NC}"
echo ""

# Offer to show the prompt
echo -e "${CYAN}─────────────────────────────────────────────────────────────────────────────${NC}"
read -p "Display the Generation 1 prompt now? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    cat "$PROMPT_FILE"
fi
