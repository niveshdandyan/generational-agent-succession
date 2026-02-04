#!/usr/bin/env python3
"""
GAS Dashboard Server Package
============================

This package provides the server-side components for the Generational Agent
Succession (GAS) Dashboard, including configuration, file tracking, output
parsing, HTTP handling, WebSocket management, and GAS status gathering.

Modules:
    config: Configuration constants and settings
    file_tracker: File position tracking for incremental reading
    output_parser: NDJSON output parsing and event extraction
    main: Main entry point with asyncio server
    http_handler: HTTP request handling for static files and API
    websocket_handler: WebSocket connection management and broadcasting
    gas_status: GAS-specific status gathering logic

Usage:
    from server import (
        GAS_DIR, GAS_NAME, GAS_MODE, PORT, HOST,
        IDLE_THRESHOLD_SECONDS, COMPLETION_THRESHOLD_SECONDS,
        COMPLETION_MARKERS, MAX_LIVE_EVENTS, MAX_CONTENT_LENGTH,
        WEBSOCKET_PING_INTERVAL, FILE_WATCH_INTERVAL
    )

    from server.file_tracker import FilePositionTracker, BoundedParseCache
    from server.output_parser import parse_output_content, ParsedOutput
    from server.http_handler import create_http_server, HTTPRequestHandler
    from server.websocket_handler import WebSocketManager
    from server.gas_status import GASStatusGatherer
    from server.main import DashboardServer, run
"""

# Version information
__version__ = '1.0.0'
__author__ = 'GAS Team'

# Import configuration constants
from .config import (
    # Environment variables
    GAS_DIR,
    GAS_NAME,
    GAS_MODE,
    TASK_DIR,
    PORT,
    HOST,

    # Timing configuration
    IDLE_THRESHOLD_SECONDS,
    COMPLETION_THRESHOLD_SECONDS,
    WEBSOCKET_PING_INTERVAL,
    FILE_WATCH_INTERVAL,

    # Resource limits
    MAX_CACHE_SIZE,
    MAX_LIVE_EVENTS,
    MAX_CONTENT_LENGTH,

    # Detection and display
    COMPLETION_MARKERS,
    TOOL_ICONS,
    STATUS_COLORS,
    WS_MESSAGE_TYPES,

    # File patterns
    WATCH_PATTERNS,
    IGNORE_PATTERNS,

    # Logging
    LOG_FORMAT,
    LOG_DATE_FORMAT,
    LOG_LEVEL,

    # API
    API_VERSION,
    API_PREFIX,

    # Helper functions
    get_gas_path,
    get_session_path,
    get_task_path,
    get_tool_icon,
    get_status_color,
    validate_config,
    get_config_summary,
)

# Import file tracker classes
from .file_tracker import (
    FileState,
    FilePositionTracker,
    BoundedParseCache,
)

# Import output parser classes and functions
from .output_parser import (
    ParsedOutput,
    parse_ndjson_line,
    extract_tool_name,
    extract_file_path,
    check_completion_markers,
    format_event_for_display,
    parse_output_content,
    parse_output_file,
)

# Import HTTP handler classes and functions
from .http_handler import (
    HTTPRequestHandler,
    AsyncHTTPServer,
    create_http_server,
    get_content_type,
)

# Import WebSocket handler classes
from .websocket_handler import (
    WebSocketConnection,
    WebSocketManager,
    FileChangeNotifier,
)

# Import GAS status gatherer
from .gas_status import (
    GASStatusGatherer,
    detect_agent_generations,
)

# Import main server
from .main import (
    DashboardServer,
    main,
    run,
)

# Define public API
__all__ = [
    # Version
    '__version__',
    '__author__',

    # Configuration - Environment
    'GAS_DIR',
    'GAS_NAME',
    'GAS_MODE',
    'TASK_DIR',
    'PORT',
    'HOST',

    # Configuration - Timing
    'IDLE_THRESHOLD_SECONDS',
    'COMPLETION_THRESHOLD_SECONDS',
    'WEBSOCKET_PING_INTERVAL',
    'FILE_WATCH_INTERVAL',

    # Configuration - Limits
    'MAX_CACHE_SIZE',
    'MAX_LIVE_EVENTS',
    'MAX_CONTENT_LENGTH',

    # Configuration - Detection/Display
    'COMPLETION_MARKERS',
    'TOOL_ICONS',
    'STATUS_COLORS',
    'WS_MESSAGE_TYPES',

    # Configuration - Patterns
    'WATCH_PATTERNS',
    'IGNORE_PATTERNS',

    # Configuration - Logging
    'LOG_FORMAT',
    'LOG_DATE_FORMAT',
    'LOG_LEVEL',

    # Configuration - API
    'API_VERSION',
    'API_PREFIX',

    # Configuration - Helper Functions
    'get_gas_path',
    'get_session_path',
    'get_task_path',
    'get_tool_icon',
    'get_status_color',
    'validate_config',
    'get_config_summary',

    # File Tracker
    'FileState',
    'FilePositionTracker',
    'BoundedParseCache',

    # Output Parser
    'ParsedOutput',
    'parse_ndjson_line',
    'extract_tool_name',
    'extract_file_path',
    'check_completion_markers',
    'format_event_for_display',
    'parse_output_content',
    'parse_output_file',

    # HTTP Handler
    'HTTPRequestHandler',
    'AsyncHTTPServer',
    'create_http_server',
    'get_content_type',

    # WebSocket Handler
    'WebSocketConnection',
    'WebSocketManager',
    'FileChangeNotifier',

    # GAS Status Gatherer
    'GASStatusGatherer',
    'detect_agent_generations',

    # Main Server
    'DashboardServer',
    'main',
    'run',
]
