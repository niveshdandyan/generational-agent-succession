#!/usr/bin/env python3
"""
File Position Tracker
=====================
Efficient incremental file reading using seek/tell for real-time streaming.
Provides memory-efficient tracking of multiple files for the GAS dashboard.
"""

import os
import threading
import logging
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class FileState:
    """Track state for a single file."""
    path: str
    position: int = 0
    last_modified: float = 0.0
    last_size: int = 0
    last_read: Optional[datetime] = None
    error_count: int = 0
    line_count: int = 0


class FilePositionTracker:
    """
    Track file positions for incremental reading.
    Memory-efficient: only stores position, not content.
    Thread-safe with internal locking.
    """

    def __init__(self, max_files: int = 100):
        self._files: Dict[str, FileState] = {}
        self._lock = threading.Lock()
        self._max_files = max_files

    def get_new_content(self, file_path: str) -> Tuple[str, bool]:
        """
        Read new content from file since last read using seek/tell.
        Returns (new_content, has_new_content).

        Uses efficient seek/tell to avoid re-reading entire files.
        """
        with self._lock:
            if not os.path.exists(file_path):
                return '', False

            try:
                stat = os.stat(file_path)
                current_size = stat.st_size
                current_mtime = stat.st_mtime

                # Get or create file state
                if file_path not in self._files:
                    self._ensure_capacity()
                    self._files[file_path] = FileState(path=file_path)

                state = self._files[file_path]

                # Check if file has new content (same mtime and size = no change)
                if current_mtime == state.last_modified and current_size == state.last_size:
                    return '', False

                # Handle file truncation (e.g., log rotation)
                if current_size < state.last_size:
                    state.position = 0
                    state.line_count = 0
                    logger.debug(f"File truncated, resetting position: {file_path}")

                # Read new content using seek
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    f.seek(state.position)
                    new_content = f.read()
                    state.position = f.tell()

                # Update state
                state.last_modified = current_mtime
                state.last_size = current_size
                state.last_read = datetime.utcnow()
                state.error_count = 0
                state.line_count += new_content.count('\n')

                return new_content, bool(new_content)

            except Exception as e:
                if file_path in self._files:
                    self._files[file_path].error_count += 1
                logger.error(f"Error reading {file_path}: {e}")
                return '', False

    def get_all_content(self, file_path: str) -> str:
        """Read entire file content (for initial load)."""
        try:
            if not os.path.exists(file_path):
                return ''
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            # Update position to end
            with self._lock:
                if file_path not in self._files:
                    self._ensure_capacity()
                    self._files[file_path] = FileState(path=file_path)
                self._files[file_path].position = len(content.encode('utf-8'))
                self._files[file_path].last_read = datetime.utcnow()

            return content
        except Exception:
            return ''

    def reset_position(self, file_path: str) -> None:
        """Reset file position to start."""
        with self._lock:
            if file_path in self._files:
                self._files[file_path].position = 0

    def get_file_info(self, file_path: str) -> Optional[FileState]:
        """Get tracking info for a file."""
        with self._lock:
            return self._files.get(file_path)

    def _ensure_capacity(self) -> None:
        """Ensure we don't exceed max files by removing oldest."""
        if len(self._files) >= self._max_files:
            # Remove oldest by last_read
            oldest = min(
                self._files.items(),
                key=lambda x: x[1].last_read or datetime.min
            )
            del self._files[oldest[0]]

    def clear(self) -> None:
        """Clear all tracked files."""
        with self._lock:
            self._files.clear()

    @property
    def tracked_count(self) -> int:
        """Return count of tracked files."""
        with self._lock:
            return len(self._files)

    def get_stats(self) -> Dict[str, int]:
        """Get tracking statistics."""
        with self._lock:
            total_errors = sum(s.error_count for s in self._files.values())
            return {
                'tracked_files': len(self._files),
                'max_files': self._max_files,
                'total_errors': total_errors
            }


class BoundedParseCache:
    """
    LRU-style cache for parsed output with bounded size.
    Prevents memory bloat from large output files.
    Thread-safe with internal locking.

    Cache keys can be:
    - Simple string keys: cache.get('key')
    - Composite keys with mtime: cache.get_with_mtime('filepath', mtime)
    """

    def __init__(self, max_size: int = 50):
        self._cache: Dict[str, dict] = {}
        self._access_order: List[str] = []
        self._lock = threading.Lock()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[dict]:
        """Get cached parse result by key."""
        with self._lock:
            if key in self._cache:
                # Move to end (most recently used)
                self._access_order.remove(key)
                self._access_order.append(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None

    def get_with_mtime(self, filepath: str, mtime: float) -> Optional[dict]:
        """Get cached result using filepath and mtime as composite key."""
        key = f"{filepath}:{mtime}"
        return self.get(key)

    def set(self, key: str, value: dict) -> None:
        """Cache a parse result."""
        with self._lock:
            if key in self._cache:
                self._access_order.remove(key)
            elif len(self._cache) >= self._max_size:
                # Remove least recently used
                oldest = self._access_order.pop(0)
                del self._cache[oldest]

            self._cache[key] = value
            self._access_order.append(key)

    def set_with_mtime(self, filepath: str, mtime: float, value: dict) -> None:
        """Cache result using filepath and mtime as composite key."""
        key = f"{filepath}:{mtime}"
        self.set(key, value)

    def invalidate(self, key: str) -> None:
        """Remove a key from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._access_order.remove(key)

    def invalidate_file(self, filepath: str) -> None:
        """Invalidate all cache entries for a specific file."""
        with self._lock:
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{filepath}:")]
            for key in keys_to_remove:
                del self._cache[key]
                self._access_order.remove(key)

    def clear(self) -> None:
        """Clear entire cache."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self._hits = 0
            self._misses = 0

    @property
    def size(self) -> int:
        """Return current cache size."""
        with self._lock:
            return len(self._cache)

    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                'size': len(self._cache),
                'max_size': self._max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate_percent': round(hit_rate, 1)
            }
