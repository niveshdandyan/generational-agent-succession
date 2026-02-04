#!/usr/bin/env python3
"""
GAS Status Gatherer
===================
GAS-specific status gathering logic for the dashboard.
Reads gas-state.json, knowledge stores, and agent output files.
"""
import asyncio
import json
import os
import glob
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging

from .config import (
    GAS_DIR,
    GAS_NAME,
    GAS_MODE,
    TASK_DIR,
    IDLE_THRESHOLD_SECONDS,
    COMPLETION_THRESHOLD_SECONDS,
    MAX_LIVE_EVENTS,
    COMPLETION_MARKERS,
)
from .file_tracker import FilePositionTracker, BoundedParseCache
from .output_parser import parse_output_content, ParsedOutput

logger = logging.getLogger(__name__)


class GASStatusGatherer:
    """
    Gather status from GAS project state and agent outputs.
    """

    def __init__(
        self,
        gas_dir: Optional[str] = None,
        task_dir: Optional[str] = None
    ):
        self.gas_dir = gas_dir or GAS_DIR
        self.task_dir = task_dir or TASK_DIR

        # File trackers
        self._file_tracker = FilePositionTracker(max_files=100)
        self._parse_cache = BoundedParseCache(max_size=50)

        # State tracking
        self._last_state_hash: str = ''
        self._last_check: Optional[datetime] = None
        self._agent_parsed: Dict[str, ParsedOutput] = {}
        self._recent_events: List[Dict[str, Any]] = []
        self._new_events: List[Dict[str, Any]] = []

        # GAS-specific paths
        self._gas_state_path = os.path.join(self.gas_dir, 'gas-state.json')
        self._knowledge_path = os.path.join(self.gas_dir, 'knowledge', 'store.json')
        self._agents_dir = os.path.join(self.gas_dir, 'agents')

    async def get_full_status(self) -> Dict[str, Any]:
        """
        Get full dashboard status including all agents.
        """
        now = datetime.utcnow()

        # Get GAS project state
        gas_state = await self._read_gas_state()

        # Get all agent statuses
        agents = await self._gather_agent_statuses()

        # Calculate overall progress
        overall_progress = self._calculate_overall_progress(agents)

        # Get waves/generations info
        waves = self._organize_by_waves(agents)

        # Get knowledge/learnings
        learnings = await self._read_knowledge_store()

        return {
            'swarm_name': gas_state.get('swarm_name', GAS_NAME),
            'swarm_mode': gas_state.get('mode', GAS_MODE),
            'overall_progress': overall_progress,
            'start_time': gas_state.get('start_time', now.isoformat() + 'Z'),
            'agents': agents,
            'waves': waves,
            'total_agents': len(agents),
            'active_agents': sum(1 for a in agents.values() if a.get('status') == 'running'),
            'completed_agents': sum(1 for a in agents.values() if a.get('status') == 'completed'),
            'learnings_count': len(learnings),
            'recent_learnings': learnings[-5:] if learnings else [],
            'timestamp': now.isoformat() + 'Z',
        }

    async def get_agent_details(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific agent.
        """
        agents = await self._gather_agent_statuses()

        # Try to find agent by ID or partial match
        agent_data = agents.get(agent_id)
        if not agent_data:
            # Try partial match
            for key, data in agents.items():
                if agent_id in key:
                    agent_data = data
                    break

        if not agent_data:
            return None

        # Add detailed output parsing
        output_file = agent_data.get('output_file')
        if output_file and os.path.exists(output_file):
            parsed = self._agent_parsed.get(agent_id)
            if parsed:
                agent_data['live_events'] = parsed.live_events
                agent_data['files_created'] = parsed.files_created
                agent_data['files_modified'] = parsed.files_modified
                agent_data['errors'] = parsed.errors

        return agent_data

    async def get_recent_events(self) -> List[Dict[str, Any]]:
        """Get recent live events from all agents."""
        return self._recent_events[-MAX_LIVE_EVENTS:]

    async def get_new_events(self) -> List[Dict[str, Any]]:
        """Get new events since last check."""
        events = self._new_events.copy()
        self._new_events.clear()
        return events

    async def check_for_changes(self) -> bool:
        """
        Check if any files have changed since last check.
        Returns True if changes detected.
        """
        has_changes = False

        # Check GAS state file
        gas_content, changed = self._file_tracker.get_new_content(self._gas_state_path)
        if changed:
            has_changes = True

        # Check agent output files
        output_files = self._find_agent_output_files()
        for output_file in output_files:
            content, changed = self._file_tracker.get_new_content(output_file)
            if changed:
                has_changes = True
                # Parse incremental content
                agent_id = self._extract_agent_id(output_file)
                if agent_id:
                    existing = self._agent_parsed.get(agent_id)
                    parsed = parse_output_content(content, existing)
                    self._agent_parsed[agent_id] = parsed

                    # Add new events
                    if parsed.live_events:
                        for event in parsed.live_events[-10:]:
                            event['agent_id'] = agent_id
                            self._new_events.append(event)
                            self._recent_events.append(event)

        # Trim recent events
        if len(self._recent_events) > MAX_LIVE_EVENTS * 2:
            self._recent_events = self._recent_events[-MAX_LIVE_EVENTS:]

        self._last_check = datetime.utcnow()
        return has_changes

    async def _read_gas_state(self) -> Dict[str, Any]:
        """Read gas-state.json file."""
        if not os.path.exists(self._gas_state_path):
            # Try alternative locations
            alt_paths = [
                os.path.join(self.gas_dir, 'swarm-config.json'),
                os.path.join(self.gas_dir, 'config.json'),
            ]
            for alt_path in alt_paths:
                if os.path.exists(alt_path):
                    self._gas_state_path = alt_path
                    break

        try:
            if os.path.exists(self._gas_state_path):
                with open(self._gas_state_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error reading GAS state: {e}")

        return {'swarm_name': GAS_NAME, 'mode': GAS_MODE}

    async def _read_knowledge_store(self) -> List[Dict[str, Any]]:
        """Read knowledge/store.json for learnings."""
        try:
            if os.path.exists(self._knowledge_path):
                with open(self._knowledge_path, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        return data.get('learnings', data.get('entries', []))
        except Exception as e:
            logger.debug(f"Could not read knowledge store: {e}")

        return []

    async def _gather_agent_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Gather status for all discovered agents."""
        agents = {}
        now = datetime.utcnow()

        # Read GAS state for agent config
        gas_state = await self._read_gas_state()
        agent_configs = gas_state.get('agents', {})

        # Find agent output files
        output_files = self._find_agent_output_files()

        # Build agent status from configs
        for agent_id, config in agent_configs.items():
            agent_data = {
                'id': agent_id,
                'role': config.get('role', 'Agent'),
                'wave': config.get('wave', 1),
                'generation': config.get('generation', 1),
                'mission': config.get('mission', ''),
                'task_id': config.get('task_id'),
                'status': 'pending',
                'progress': 0,
                'current_task': '',
                'tools_used': {},
                'files_created': [],
                'files_modified': [],
                'last_activity': None,
                'output_file': None,
            }

            # Try to find output file for this agent
            task_id = config.get('task_id')
            if task_id:
                for output_file in output_files:
                    if task_id in output_file:
                        agent_data['output_file'] = output_file
                        break

            # Parse output file if found
            output_file = agent_data.get('output_file')
            if output_file and os.path.exists(output_file):
                parsed = self._parse_agent_output(output_file, agent_id)

                agent_data['status'] = self._determine_agent_status(parsed, now)
                agent_data['progress'] = parsed.progress_estimate
                agent_data['current_task'] = parsed.current_task
                agent_data['tools_used'] = parsed.tools_used
                agent_data['files_created'] = parsed.files_created
                agent_data['files_modified'] = parsed.files_modified
                agent_data['has_completion'] = parsed.has_completion_marker

                if parsed.last_activity:
                    agent_data['last_activity'] = parsed.last_activity.isoformat() + 'Z'

            agents[agent_id] = agent_data

        # Also discover any agents from output files not in config
        for output_file in output_files:
            agent_id = self._extract_agent_id(output_file)
            if agent_id and agent_id not in agents:
                parsed = self._parse_agent_output(output_file, agent_id)
                agents[agent_id] = {
                    'id': agent_id,
                    'role': 'Agent',
                    'wave': 1,
                    'generation': 1,
                    'mission': '',
                    'task_id': agent_id,
                    'status': self._determine_agent_status(parsed, now),
                    'progress': parsed.progress_estimate,
                    'current_task': parsed.current_task,
                    'tools_used': parsed.tools_used,
                    'files_created': parsed.files_created,
                    'files_modified': parsed.files_modified,
                    'has_completion': parsed.has_completion_marker,
                    'last_activity': parsed.last_activity.isoformat() + 'Z' if parsed.last_activity else None,
                    'output_file': output_file,
                }

        return agents

    def _find_agent_output_files(self) -> List[str]:
        """Find all agent output files in task directory."""
        output_files = []

        # Check task directory patterns
        patterns = [
            os.path.join(self.task_dir, '**/output.ndjson'),
            os.path.join(self.task_dir, '**/output.jsonl'),
            os.path.join(self.task_dir, '*/output'),
            os.path.join(self.task_dir, '*/output.ndjson'),
            os.path.join(self.gas_dir, 'output', '*.ndjson'),
            os.path.join(self.gas_dir, 'output', '*', 'output.ndjson'),
        ]

        for pattern in patterns:
            output_files.extend(glob.glob(pattern, recursive=True))

        # Deduplicate
        return list(set(output_files))

    def _extract_agent_id(self, output_file: str) -> Optional[str]:
        """Extract agent ID from output file path."""
        parts = Path(output_file).parts
        for i, part in enumerate(parts):
            if part.startswith('a') and len(part) == 7:
                return part
            if 'agent' in part.lower():
                return part

        # Use directory name
        return Path(output_file).parent.name

    def _parse_agent_output(self, output_file: str, agent_id: str) -> ParsedOutput:
        """Parse an agent output file with caching."""
        # Check cache
        cache_key = f"{output_file}:{os.path.getmtime(output_file)}"
        cached = self._parse_cache.get(cache_key)
        if cached:
            return ParsedOutput(**cached)

        # Get content and parse
        content = self._file_tracker.get_all_content(output_file)
        parsed = parse_output_content(content)

        # Store in cache and agent parsed dict
        self._parse_cache.set(cache_key, {
            'total_events': parsed.total_events,
            'tools_used': parsed.tools_used,
            'files_created': parsed.files_created,
            'files_modified': parsed.files_modified,
            'live_events': parsed.live_events,
            'last_activity': parsed.last_activity,
            'has_completion_marker': parsed.has_completion_marker,
            'progress_estimate': parsed.progress_estimate,
            'current_task': parsed.current_task,
            'errors': parsed.errors,
            'raw_lines_count': parsed.raw_lines_count,
        })

        self._agent_parsed[agent_id] = parsed
        return parsed

    def _determine_agent_status(self, parsed: ParsedOutput, now: datetime) -> str:
        """Determine agent status based on parsed output."""
        if parsed.has_completion_marker:
            return 'completed'

        if not parsed.last_activity:
            if parsed.total_events == 0:
                return 'pending'
            return 'idle'

        # Calculate time since last activity
        if parsed.last_activity.tzinfo is None:
            last_activity = parsed.last_activity.replace(tzinfo=timezone.utc)
        else:
            last_activity = parsed.last_activity

        now_utc = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now
        seconds_since_activity = (now_utc - last_activity).total_seconds()

        if seconds_since_activity > COMPLETION_THRESHOLD_SECONDS:
            return 'completed' if parsed.total_events > 20 else 'idle'
        elif seconds_since_activity > IDLE_THRESHOLD_SECONDS:
            return 'idle'
        else:
            return 'running'

    def _calculate_overall_progress(self, agents: Dict[str, Dict[str, Any]]) -> int:
        """Calculate overall progress percentage."""
        if not agents:
            return 0

        total_progress = sum(a.get('progress', 0) for a in agents.values())
        completed = sum(1 for a in agents.values() if a.get('status') == 'completed')

        # Weight completion more heavily
        completion_bonus = (completed / len(agents)) * 50 if agents else 0
        avg_progress = (total_progress / len(agents)) * 0.5 if agents else 0

        return min(100, int(avg_progress + completion_bonus))

    def _organize_by_waves(self, agents: Dict[str, Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        """Organize agents by wave/generation."""
        waves: Dict[int, Dict[str, Any]] = {}

        for agent_id, agent_data in agents.items():
            wave = agent_data.get('wave', 1)

            if wave not in waves:
                waves[wave] = {
                    'wave': wave,
                    'agents': [],
                    'total': 0,
                    'running': 0,
                    'completed': 0,
                    'idle': 0,
                    'pending': 0,
                }

            wave_data = waves[wave]
            wave_data['agents'].append(agent_id)
            wave_data['total'] += 1

            status = agent_data.get('status', 'pending')
            if status in wave_data:
                wave_data[status] += 1

        return waves


def detect_agent_generations(agents: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detect agent generations and successions.
    Returns list of generation events.
    """
    generations = []

    for agent_id, agent_data in agents.items():
        gen = agent_data.get('generation', 1)
        if gen > 1:
            generations.append({
                'agent_id': agent_id,
                'generation': gen,
                'role': agent_data.get('role'),
                'parent': agent_data.get('parent_agent'),
                'timestamp': agent_data.get('start_time'),
            })

    return sorted(generations, key=lambda x: (x['generation'], x['agent_id']))
