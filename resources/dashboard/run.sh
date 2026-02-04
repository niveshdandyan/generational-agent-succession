#!/usr/bin/env bash
# ==============================================================================
# GAS Dashboard Server - Launch Script
# ==============================================================================
# This script sets up the environment and starts the GAS Dashboard server.
#
# Usage:
#   ./run.sh                    # Start with default settings
#   ./run.sh --port 8080        # Override port
#   ./run.sh --help             # Show help
#
# Environment Variables:
#   GAS_DIR                     # Base directory for GAS operations
#   GAS_NAME                    # Name of the current GAS session
#   GAS_MODE                    # Operating mode (swarm, sequential, interactive)
#   DASHBOARD_PORT              # Server port (default: 8080)
#   DASHBOARD_HOST              # Server host (default: 0.0.0.0)
#   GAS_LOG_LEVEL               # Logging level (default: INFO)
# ==============================================================================

set -e

# Script directory (where this script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default environment variables
export GAS_DIR="${GAS_DIR:-/workspace/project-gas}"
export GAS_NAME="${GAS_NAME:-GAS Project}"
export GAS_MODE="${GAS_MODE:-swarm}"
export DASHBOARD_PORT="${DASHBOARD_PORT:-8080}"
export DASHBOARD_HOST="${DASHBOARD_HOST:-0.0.0.0}"
export GAS_LOG_LEVEL="${GAS_LOG_LEVEL:-INFO}"

# Parse command-line arguments
show_help() {
    cat << EOF
GAS Dashboard Server

Usage: $(basename "$0") [OPTIONS]

Options:
    -p, --port PORT     Set server port (default: $DASHBOARD_PORT)
    -h, --host HOST     Set server host (default: $DASHBOARD_HOST)
    -d, --dir DIR       Set GAS directory (default: $GAS_DIR)
    -n, --name NAME     Set GAS session name (default: $GAS_NAME)
    -m, --mode MODE     Set GAS mode (default: $GAS_MODE)
    -l, --log-level LVL Set log level (default: $GAS_LOG_LEVEL)
    --help              Show this help message

Environment Variables:
    GAS_DIR             Base directory for GAS operations
    GAS_NAME            Name of the current GAS session
    GAS_MODE            Operating mode (swarm, sequential, interactive)
    DASHBOARD_PORT      Server port
    DASHBOARD_HOST      Server host
    GAS_LOG_LEVEL       Logging level (DEBUG, INFO, WARNING, ERROR)

Examples:
    $(basename "$0")                              # Start with defaults
    $(basename "$0") --port 9000                  # Custom port
    $(basename "$0") -d /path/to/gas -n "MyGAS"  # Custom GAS path and name

EOF
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--port)
            export DASHBOARD_PORT="$2"
            shift 2
            ;;
        -h|--host)
            export DASHBOARD_HOST="$2"
            shift 2
            ;;
        -d|--dir)
            export GAS_DIR="$2"
            shift 2
            ;;
        -n|--name)
            export GAS_NAME="$2"
            shift 2
            ;;
        -m|--mode)
            export GAS_MODE="$2"
            shift 2
            ;;
        -l|--log-level)
            export GAS_LOG_LEVEL="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Banner
echo "=============================================="
echo "       GAS Dashboard Server v2.0"
echo "=============================================="
echo ""
echo "Configuration:"
echo "  GAS Directory:  $GAS_DIR"
echo "  GAS Name:       $GAS_NAME"
echo "  GAS Mode:       $GAS_MODE"
echo "  HTTP Port:      $DASHBOARD_PORT"
echo "  WebSocket Port: $((DASHBOARD_PORT + 1))"
echo "  Host:           $DASHBOARD_HOST"
echo "  Log Level:      $GAS_LOG_LEVEL"
echo ""
echo "Starting server..."
echo "----------------------------------------------"
echo ""

# Change to script directory
cd "$SCRIPT_DIR"

# Check if Python dependencies are installed
if ! python3 -c "import websockets" 2>/dev/null; then
    echo "Warning: websockets package not installed."
    echo "Installing dependencies..."
    pip install -r requirements.txt --break-system-packages -q 2>/dev/null || \
    pip install -r requirements.txt -q 2>/dev/null || \
    echo "Could not install dependencies. Please install manually: pip install -r requirements.txt"
fi

# Run the server
exec python3 -m server.main
