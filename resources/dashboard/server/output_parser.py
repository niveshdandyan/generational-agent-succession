#!/usr/bin/env python3
"""
Output Parser
=============
Parse agent output files (NDJSON format) to extract events, tools, and progress.
Designed for efficient line-by-line parsing of Claude Code agent output.
"""

import json
import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field

from .config import COMPLETION_MARKERS, MAX_CONTENT_LENGTH, MAX_LIVE_EVENTS

logger = logging.getLogger(__name__)


@dataclass
class ParsedOutput:
    """Structured output from parsing an agent's output file."""
    total_events: int = 0
    tools_used: Dict[str, int] = field(default_factory=dict)
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    live_events: List[dict] = field(default_factory=list)
    last_activity: Optional[datetime] = None
    has_completion_marker: bool = False
    progress_estimate: int = 0
    current_task: str = ''
    errors: List[str] = field(default_factory=list)
    raw_lines_count: int = 0
    assistant_messages: int = 0
    tool_results: int = 0


def parse_ndjson_line(line: str) -> Optional[dict]:
    """Parse a single NDJSON line, handling malformed JSON gracefully."""
    line = line.strip()
    if not line:
        return None

    try:
        return json.loads(line)
    except json.JSONDecodeError:
        # Try to extract partial info from malformed lines
        return None


def extract_tool_name(event: dict) -> Optional[str]:
    """Extract tool name from various event formats."""
    # Standard format
    if 'type' in event:
        if event['type'] == 'tool_use':
            return event.get('name') or event.get('tool')
        if event['type'] == 'assistant' and 'content' in event:
            content = event['content']
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'tool_use':
                        return item.get('name')

    # Direct tool field
    if 'tool' in event:
        return event['tool']

    # Direct name field (from tool invocation)
    if 'name' in event and event.get('type') != 'assistant':
        return event['name']

    # Nested in message (assistant message format)
    if 'message' in event and isinstance(event['message'], dict):
        msg = event['message']
        # Check message content for tool_use items
        if 'content' in msg and isinstance(msg['content'], list):
            for item in msg['content']:
                if isinstance(item, dict) and item.get('type') == 'tool_use':
                    return item.get('name')
        return extract_tool_name(msg)

    return None


def extract_all_tools_from_event(event: dict) -> List[Tuple[str, Optional[dict]]]:
    """
    Extract all tool usages from an event (handles multiple tools in one message).
    Returns list of (tool_name, input_data) tuples.
    """
    tools = []

    # Direct tool_use event
    if event.get('type') == 'tool_use':
        tools.append((event.get('name', 'unknown'), event.get('input')))
        return tools

    # Check assistant message content for multiple tool_use items
    if event.get('type') == 'assistant':
        content = event.get('content', [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'tool_use':
                    tools.append((item.get('name', 'unknown'), item.get('input')))

        # Also check nested message format
        if 'message' in event:
            msg = event['message']
            if isinstance(msg, dict) and 'content' in msg:
                msg_content = msg['content']
                if isinstance(msg_content, list):
                    for item in msg_content:
                        if isinstance(item, dict) and item.get('type') == 'tool_use':
                            tools.append((item.get('name', 'unknown'), item.get('input')))

    return tools


def extract_file_path(event: dict) -> Optional[str]:
    """Extract file path from Write/Edit tool events."""
    # Check input parameters
    if 'input' in event and isinstance(event['input'], dict):
        return event['input'].get('file_path') or event['input'].get('path')

    # Check content for file operations
    if 'content' in event:
        content = event['content']
        if isinstance(content, str):
            # Look for file paths in content
            match = re.search(r'(?:Writing|Created|Edited|Modified).*?["\']?(/[^\s"\']+)["\']?', content)
            if match:
                return match.group(1)

    return None


def check_completion_markers(text: str) -> bool:
    """Check if text contains any completion marker."""
    text_lower = text.lower()
    for marker in COMPLETION_MARKERS:
        if marker.lower() in text_lower:
            return True
    return False


def format_event_for_display(event: dict, max_length: int = MAX_CONTENT_LENGTH) -> dict:
    """Format an event for display in the live feed."""
    formatted = {
        'timestamp': event.get('timestamp', datetime.utcnow().isoformat()),
        'type': 'unknown',
        'content': '',
        'tool': None,
    }

    # Determine event type and content
    if 'type' in event:
        event_type = event['type']

        if event_type == 'tool_use':
            formatted['type'] = 'tool'
            formatted['tool'] = event.get('name') or event.get('tool', 'Unknown')

            # Get tool input summary
            if 'input' in event and isinstance(event['input'], dict):
                input_data = event['input']
                if 'file_path' in input_data:
                    formatted['content'] = f"File: {input_data['file_path']}"
                elif 'command' in input_data:
                    cmd = input_data['command'][:100]
                    formatted['content'] = f"Command: {cmd}"
                elif 'pattern' in input_data:
                    formatted['content'] = f"Pattern: {input_data['pattern']}"
                elif 'prompt' in input_data:
                    formatted['content'] = f"Prompt: {input_data['prompt'][:80]}..."
                else:
                    formatted['content'] = str(input_data)[:max_length]
            else:
                formatted['content'] = f"Using {formatted['tool']}"

        elif event_type == 'tool_result':
            formatted['type'] = 'result'
            content = event.get('content', '')
            if isinstance(content, str):
                formatted['content'] = content[:max_length]
            elif isinstance(content, dict):
                formatted['content'] = json.dumps(content)[:max_length]
            else:
                formatted['content'] = str(content)[:max_length]

        elif event_type == 'assistant':
            formatted['type'] = 'thinking'
            content = event.get('content', '')
            if isinstance(content, str):
                formatted['content'] = content[:max_length]
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        formatted['content'] = item.get('text', '')[:max_length]
                        break

        elif event_type == 'text':
            formatted['type'] = 'text'
            formatted['content'] = event.get('text', '')[:max_length]

    # Truncate content if needed
    if len(formatted['content']) > max_length:
        formatted['content'] = formatted['content'][:max_length] + '...'

    return formatted


def parse_output_content(content: str, existing_parsed: Optional[ParsedOutput] = None) -> ParsedOutput:
    """
    Parse output content (NDJSON format) and extract structured information.
    Can be used incrementally by passing existing_parsed.

    Uses line-by-line parsing for memory efficiency.
    """
    result = existing_parsed or ParsedOutput()

    lines = content.split('\n')
    result.raw_lines_count += len(lines)

    for line in lines:
        event = parse_ndjson_line(line)
        if not event:
            continue

        result.total_events += 1

        # Update last activity timestamp
        timestamp = event.get('timestamp')
        if timestamp:
            try:
                if isinstance(timestamp, str):
                    ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    if not result.last_activity or ts > result.last_activity:
                        result.last_activity = ts
            except (ValueError, AttributeError):
                pass

        # Track event types
        event_type = event.get('type')
        if event_type == 'assistant':
            result.assistant_messages += 1
        elif event_type == 'tool_result':
            result.tool_results += 1

        # Extract all tools from event (handles multiple tools per message)
        tools = extract_all_tools_from_event(event)
        for tool_name, input_data in tools:
            result.tools_used[tool_name] = result.tools_used.get(tool_name, 0) + 1

            # Extract file operations from tool input
            if tool_name in ('Write', 'Edit', 'NotebookEdit') and input_data:
                file_path = None
                if isinstance(input_data, dict):
                    file_path = input_data.get('file_path') or input_data.get('notebook_path')
                if file_path:
                    if tool_name == 'Write' and file_path not in result.files_created:
                        result.files_created.append(file_path)
                    elif tool_name == 'Edit' and file_path not in result.files_modified:
                        result.files_modified.append(file_path)

            # Extract current task from TodoWrite
            if tool_name == 'TodoWrite' and input_data:
                todos = input_data.get('todos', []) if isinstance(input_data, dict) else []
                for todo in todos:
                    if isinstance(todo, dict) and todo.get('status') == 'in_progress':
                        result.current_task = todo.get('activeForm', todo.get('content', ''))
                        break

        # Fallback: single tool extraction for simpler event formats
        if not tools:
            tool_name = extract_tool_name(event)
            if tool_name:
                result.tools_used[tool_name] = result.tools_used.get(tool_name, 0) + 1
                # Extract file operations
                if tool_name in ('Write', 'Edit', 'NotebookEdit'):
                    file_path = extract_file_path(event)
                    if file_path:
                        if tool_name == 'Write' and file_path not in result.files_created:
                            result.files_created.append(file_path)
                        elif tool_name == 'Edit' and file_path not in result.files_modified:
                            result.files_modified.append(file_path)

        # Check for completion markers
        event_str = json.dumps(event)
        if check_completion_markers(event_str):
            result.has_completion_marker = True

        # Check for errors
        if event.get('type') == 'error' or event.get('is_error'):
            error_msg = event.get('message', event.get('content', str(event)))
            if isinstance(error_msg, str) and len(error_msg) < 200:
                result.errors.append(error_msg[:200])

        # Add to live events (keep most recent)
        formatted = format_event_for_display(event)
        if formatted['content']:  # Only add if has content
            result.live_events.append(formatted)
            if len(result.live_events) > MAX_LIVE_EVENTS:
                result.live_events.pop(0)

    # Estimate progress based on events and tool usage
    result.progress_estimate = estimate_progress(result)

    return result


def estimate_progress(parsed: ParsedOutput) -> int:
    """
    Estimate task progress based on parsed output.
    Uses multiple signals for better accuracy.
    """
    if parsed.has_completion_marker:
        return 100

    # Base progress on total tool usage
    total_tools = sum(parsed.tools_used.values())
    progress = min(60, total_tools * 3)

    # Boost for file creation (indicates concrete work)
    progress += min(20, len(parsed.files_created) * 5)

    # Boost for file modifications
    progress += min(10, len(parsed.files_modified) * 2)

    # Boost for TodoWrite usage (indicates structured work)
    if parsed.current_task:
        progress += 5

    # Cap at 95% until completion marker
    return min(95, progress)


def parse_output_file(file_path: str) -> ParsedOutput:
    """Parse an entire output file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return parse_output_content(content)
    except Exception as e:
        result = ParsedOutput()
        result.errors.append(f"Failed to parse: {str(e)}")
        return result


def parse_incremental(file_path: str, tracker: Any, cache: Any) -> ParsedOutput:
    """
    Parse file incrementally using FilePositionTracker and BoundedParseCache.
    This is the main entry point for efficient streaming parsing.

    Args:
        file_path: Path to the output file
        tracker: FilePositionTracker instance
        cache: BoundedParseCache instance

    Returns:
        ParsedOutput with accumulated results
    """
    import os

    if not os.path.exists(file_path):
        return ParsedOutput()

    # Check cache first
    mtime = os.path.getmtime(file_path)
    cached = cache.get_with_mtime(file_path, mtime)
    if cached:
        return ParsedOutput(**cached)

    # Get new content since last read
    new_content, has_new = tracker.get_new_content(file_path)

    # If no new content, try to return existing cached result
    if not has_new:
        # Return from cache with any mtime
        for key in list(cache._cache.keys()):
            if key.startswith(f"{file_path}:"):
                data = cache._cache[key]
                return ParsedOutput(**data)
        # No cache, parse entire file
        result = parse_output_file(file_path)
    else:
        # Parse new content incrementally
        result = parse_output_content(new_content)

    # Cache result
    cache.set_with_mtime(file_path, mtime, {
        'total_events': result.total_events,
        'tools_used': result.tools_used,
        'files_created': result.files_created,
        'files_modified': result.files_modified,
        'live_events': result.live_events,
        'last_activity': result.last_activity.isoformat() if result.last_activity else None,
        'has_completion_marker': result.has_completion_marker,
        'progress_estimate': result.progress_estimate,
        'current_task': result.current_task,
        'errors': result.errors,
        'raw_lines_count': result.raw_lines_count,
        'assistant_messages': result.assistant_messages,
        'tool_results': result.tool_results
    })

    return result


def to_dict(parsed: ParsedOutput) -> dict:
    """Convert ParsedOutput to dictionary for JSON serialization."""
    return {
        'total_events': parsed.total_events,
        'tools_used': parsed.tools_used,
        'files_created': parsed.files_created,
        'files_modified': parsed.files_modified,
        'live_events': parsed.live_events,
        'last_activity': parsed.last_activity.isoformat() if parsed.last_activity else None,
        'has_completion_marker': parsed.has_completion_marker,
        'progress_estimate': parsed.progress_estimate,
        'current_task': parsed.current_task,
        'errors': parsed.errors,
        'raw_lines_count': parsed.raw_lines_count,
        'assistant_messages': parsed.assistant_messages,
        'tool_results': parsed.tool_results
    }


def get_activity_summary(parsed: ParsedOutput) -> str:
    """Generate a human-readable activity summary."""
    if parsed.current_task:
        return parsed.current_task

    if parsed.has_completion_marker:
        return "Task completed"

    # Generate summary from recent activity
    if parsed.live_events:
        last_event = parsed.live_events[-1]
        if last_event.get('tool'):
            return f"Using {last_event['tool']}"
        if last_event.get('content'):
            content = last_event['content'][:80]
            return f"{content}..." if len(last_event['content']) > 80 else content

    total_tools = sum(parsed.tools_used.values())
    if total_tools > 0:
        return f"Working... ({total_tools} tool calls)"

    return "Initializing..."
