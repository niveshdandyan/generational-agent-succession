#!/usr/bin/env python3
"""
GAS Dashboard Configuration
===========================
Centralized configuration for the GAS dashboard server.

This module contains all configuration constants and settings for the
Generational Agent Succession (GAS) Dashboard server.

Environment Variables:
    GAS_DIR: Base directory for GAS operations
    GAS_NAME: Name of the current GAS session
    GAS_MODE: Operating mode (e.g., 'swarm', 'sequential', 'interactive')
    GAS_DASHBOARD_PORT: Server port (default: 8080)
    GAS_DASHBOARD_HOST: Server host (default: 0.0.0.0)
    TASK_DIR: Directory for task outputs (default: /tmp/claude-1000)
    GAS_LOG_LEVEL: Logging level (default: INFO)
"""

import os
from typing import Dict, List, Any, Optional


# =============================================================================
# Environment Variables with Defaults
# =============================================================================

# Server Configuration
PORT: int = int(os.getenv('DASHBOARD_PORT', os.getenv('GAS_DASHBOARD_PORT', '8080')))
HOST: str = os.getenv('DASHBOARD_HOST', os.getenv('GAS_DASHBOARD_HOST', '0.0.0.0'))

# GAS Configuration
GAS_DIR: str = os.getenv('GAS_DIR', '/workspace/project-gas')
GAS_NAME: str = os.getenv('GAS_NAME', 'GAS Project')
GAS_MODE: str = os.getenv('GAS_MODE', 'swarm')  # 'swarm' or 'sequential'
TASK_DIR: str = os.getenv('TASK_DIR', '/tmp/claude-1000')


# =============================================================================
# Timing Configuration (in seconds)
# =============================================================================

# Agent activity thresholds
IDLE_THRESHOLD_SECONDS: int = 60  # Time before agent is considered idle
COMPLETION_THRESHOLD_SECONDS: int = 120  # Time before agent is considered complete

# WebSocket configuration
WEBSOCKET_PING_INTERVAL: int = 30  # Interval for WebSocket keepalive pings

# File watching configuration
FILE_WATCH_INTERVAL: float = 0.5  # Interval for checking file changes


# =============================================================================
# Resource Limits
# =============================================================================

MAX_CACHE_SIZE: int = 50  # Maximum number of cached entries
MAX_LIVE_EVENTS: int = 50  # Maximum number of live events to store
MAX_CONTENT_LENGTH: int = 300  # Maximum content length for display


# =============================================================================
# Completion Detection
# =============================================================================

# Markers that indicate an agent has completed its task
COMPLETION_MARKERS: List[str] = [
    'EVOLUTION COMPLETE',
    'Task completed',
    'All tasks completed',
    'status": "completed"',
    'Successfully completed',
    'Finished all',
    'COMPLETED',
    'Done!',
    'Generation complete',
    'Agent complete',
    'Complete.',
    'Finished.',
    'Mission accomplished',
    'Operation complete',
    'Process complete',
    'Execution finished',
]


# =============================================================================
# Tool Icons for UI
# =============================================================================

# Map tool names to their display icons (Lucide icon names)
TOOL_ICONS: Dict[str, str] = {
    # File operations
    'Read': 'file-text',
    'Write': 'file-plus',
    'Edit': 'edit',
    'Glob': 'folder-search',
    'Grep': 'search',

    # Execution
    'Bash': 'terminal',
    'Task': 'users',
    'TodoWrite': 'check-square',

    # Web and network
    'WebFetch': 'globe',
    'WebSearch': 'search-code',

    # Code and analysis
    'NotebookEdit': 'book-open',
    'Skill': 'zap',

    # Default
    'default': 'tool',
}


# =============================================================================
# Status Colors (for UI rendering)
# =============================================================================

# Matching frontend CSS variables
STATUS_COLORS: Dict[str, str] = {
    # Agent states
    'running': '#FF6B4A',       # Orange-red - actively working
    'active': '#FF6B4A',        # Alias for running
    'idle': '#7BA3A8',          # Blue-gray - waiting/idle
    'completed': '#7D9B76',     # Green - task completed
    'failed': '#C67A6B',        # Red - error state
    'error': '#C67A6B',         # Alias for failed
    'pending': '#9B8B7A',       # Brown-gray - not started
    'needs_succession': '#D4A76A',  # Gold - needs handoff

    # Tool execution states
    'success': '#7D9B76',       # Green - tool succeeded
    'failure': '#C67A6B',       # Red - tool failed
    'timeout': '#D4A76A',       # Gold - tool timed out
}


# =============================================================================
# WebSocket Message Types
# =============================================================================

WS_MESSAGE_TYPES: Dict[str, str] = {
    'AGENT_UPDATE': 'agent_update',
    'TOOL_EXECUTION': 'tool_execution',
    'LOG_ENTRY': 'log_entry',
    'STATUS_CHANGE': 'status_change',
    'ERROR': 'error',
    'HEARTBEAT': 'heartbeat',
    'INITIAL_STATE': 'initial_state',
    'FILE_CHANGE': 'file_change',
}


# =============================================================================
# File Patterns
# =============================================================================

# Patterns for files to watch in the GAS directory
WATCH_PATTERNS: List[str] = [
    '*.json',
    '*.log',
    '*.md',
    'status.json',
    'agents/*/status.json',
    'output.jsonl',
    '*.ndjson',
]

# Files to ignore during watching
IGNORE_PATTERNS: List[str] = [
    '*.pyc',
    '__pycache__',
    '.git',
    '*.tmp',
    '*.swp',
    '.DS_Store',
    'node_modules',
]


# =============================================================================
# Logging Configuration
# =============================================================================

LOG_FORMAT: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT: str = '%Y-%m-%d %H:%M:%S'
LOG_LEVEL: str = os.getenv('GAS_LOG_LEVEL', 'INFO')


# =============================================================================
# API Configuration
# =============================================================================

API_VERSION: str = 'v1'
API_PREFIX: str = f'/api/{API_VERSION}'


# =============================================================================
# Helper Functions
# =============================================================================

def get_gas_path(*parts: str) -> str:
    """
    Construct a path relative to GAS_DIR.

    Args:
        *parts: Path components to join

    Returns:
        Full path under GAS_DIR
    """
    return os.path.join(GAS_DIR, *parts)


def get_session_path(*parts: str) -> str:
    """
    Construct a path relative to the current GAS session.

    Args:
        *parts: Path components to join

    Returns:
        Full path under the current session directory
    """
    return os.path.join(GAS_DIR, GAS_NAME, *parts)


def get_task_path(*parts: str) -> str:
    """
    Construct a path relative to TASK_DIR.

    Args:
        *parts: Path components to join

    Returns:
        Full path under TASK_DIR
    """
    return os.path.join(TASK_DIR, *parts)


def get_tool_icon(tool_name: str) -> str:
    """
    Get the icon for a given tool name.

    Args:
        tool_name: Name of the tool

    Returns:
        Icon string for the tool
    """
    return TOOL_ICONS.get(tool_name, TOOL_ICONS.get('default', 'tool'))


def get_status_color(status: str) -> str:
    """
    Get the color for a given status.

    Args:
        status: Status string

    Returns:
        Hex color code for the status
    """
    return STATUS_COLORS.get(status.lower(), STATUS_COLORS.get('pending', '#9B8B7A'))


# =============================================================================
# Configuration Validation
# =============================================================================

def validate_config() -> Dict[str, Any]:
    """
    Validate the current configuration and return a status report.

    Returns:
        Dictionary with validation results
    """
    issues: List[str] = []
    warnings: List[str] = []

    # Check GAS_DIR exists or can be created
    if not os.path.exists(GAS_DIR):
        warnings.append(f'GAS_DIR does not exist: {GAS_DIR}')

    # Check TASK_DIR exists
    if not os.path.exists(TASK_DIR):
        warnings.append(f'TASK_DIR does not exist: {TASK_DIR}')

    # Validate timing settings
    if IDLE_THRESHOLD_SECONDS <= 0:
        issues.append('IDLE_THRESHOLD_SECONDS must be positive')

    if COMPLETION_THRESHOLD_SECONDS <= IDLE_THRESHOLD_SECONDS:
        warnings.append('COMPLETION_THRESHOLD_SECONDS should be greater than IDLE_THRESHOLD_SECONDS')

    if FILE_WATCH_INTERVAL <= 0:
        issues.append('FILE_WATCH_INTERVAL must be positive')

    if WEBSOCKET_PING_INTERVAL <= 0:
        issues.append('WEBSOCKET_PING_INTERVAL must be positive')

    # Validate resource limits
    if MAX_CACHE_SIZE <= 0:
        issues.append('MAX_CACHE_SIZE must be positive')

    if MAX_LIVE_EVENTS <= 0:
        issues.append('MAX_LIVE_EVENTS must be positive')

    if MAX_CONTENT_LENGTH <= 0:
        issues.append('MAX_CONTENT_LENGTH must be positive')

    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'config': {
            'GAS_DIR': GAS_DIR,
            'GAS_NAME': GAS_NAME,
            'GAS_MODE': GAS_MODE,
            'TASK_DIR': TASK_DIR,
            'PORT': PORT,
            'HOST': HOST,
        }
    }


def get_config_summary() -> Dict[str, Any]:
    """
    Get a summary of all configuration values.

    Returns:
        Dictionary with all configuration values
    """
    return {
        'server': {
            'port': PORT,
            'host': HOST,
            'api_prefix': API_PREFIX,
        },
        'gas': {
            'dir': GAS_DIR,
            'name': GAS_NAME,
            'mode': GAS_MODE,
            'task_dir': TASK_DIR,
        },
        'timing': {
            'idle_threshold': IDLE_THRESHOLD_SECONDS,
            'completion_threshold': COMPLETION_THRESHOLD_SECONDS,
            'websocket_ping': WEBSOCKET_PING_INTERVAL,
            'file_watch': FILE_WATCH_INTERVAL,
        },
        'limits': {
            'max_cache': MAX_CACHE_SIZE,
            'max_events': MAX_LIVE_EVENTS,
            'max_content': MAX_CONTENT_LENGTH,
        },
        'logging': {
            'level': LOG_LEVEL,
            'format': LOG_FORMAT,
        }
    }
