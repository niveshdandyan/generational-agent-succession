/**
 * GAS Dashboard - Utility Functions
 * Common helper functions for the dashboard application
 */

/**
 * Format a timestamp as relative time (e.g., "5 minutes ago")
 * @param {number|string|Date} timestamp - The timestamp to format
 * @returns {string} Formatted relative time string
 */
function formatTimeAgo(timestamp) {
  if (!timestamp) return 'N/A';

  const date = new Date(timestamp);
  const now = new Date();
  const seconds = Math.floor((now - date) / 1000);

  if (seconds < 0) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;

  return date.toLocaleDateString();
}

/**
 * Format a duration in milliseconds to human-readable format
 * @param {number} ms - Duration in milliseconds
 * @returns {string} Formatted duration string
 */
function formatDuration(ms) {
  if (!ms || ms < 0) return '--:--';

  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (hours > 0) {
    return `${hours}:${String(minutes % 60).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
  }

  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`;
}

/**
 * Format elapsed time from a start timestamp
 * @param {number|string|Date} startTime - The start timestamp
 * @returns {string} Formatted elapsed time
 */
function formatElapsed(startTime) {
  if (!startTime) return '--:--';

  const start = new Date(startTime);
  const now = new Date();
  const elapsed = now - start;

  return formatDuration(elapsed);
}

/**
 * Format a number with appropriate abbreviation (K, M, B)
 * @param {number} n - Number to format
 * @param {number} decimals - Number of decimal places
 * @returns {string} Formatted number string
 */
function formatNumber(n, decimals = 1) {
  if (n === null || n === undefined) return '0';
  if (n < 1000) return String(n);
  if (n < 1000000) return (n / 1000).toFixed(decimals) + 'K';
  if (n < 1000000000) return (n / 1000000).toFixed(decimals) + 'M';
  return (n / 1000000000).toFixed(decimals) + 'B';
}

/**
 * Format a percentage value
 * @param {number} value - Value (0-100 or 0-1)
 * @param {boolean} isDecimal - Whether value is already decimal (0-1)
 * @returns {string} Formatted percentage string
 */
function formatPercentage(value, isDecimal = false) {
  if (value === null || value === undefined) return '0%';
  const percentage = isDecimal ? value * 100 : value;
  return `${Math.round(percentage)}%`;
}

/**
 * Create a debounced version of a function
 * @param {Function} fn - Function to debounce
 * @param {number} delay - Delay in milliseconds
 * @returns {Function} Debounced function
 */
function debounce(fn, delay) {
  let timeoutId;
  return function (...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * Create a throttled version of a function
 * @param {Function} fn - Function to throttle
 * @param {number} limit - Minimum time between calls in milliseconds
 * @returns {Function} Throttled function
 */
function throttle(fn, limit) {
  let inThrottle;
  return function (...args) {
    if (!inThrottle) {
      fn.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

/**
 * Escape HTML special characters to prevent XSS
 * @param {string} str - String to escape
 * @returns {string} Escaped string
 */
function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Get CSS class for agent status
 * @param {string} status - Agent status
 * @returns {string} CSS class name
 */
function getStatusClass(status) {
  const statusMap = {
    'running': 'status-running',
    'completed': 'status-completed',
    'failed': 'status-failed',
    'error': 'status-failed',
    'pending': 'status-pending',
    'idle': 'status-idle',
    'waiting': 'status-pending',
    'queued': 'status-pending'
  };

  return statusMap[status?.toLowerCase()] || 'status-pending';
}

/**
 * Get status badge class
 * @param {string} status - Agent status
 * @returns {string} Badge class name
 */
function getStatusBadgeClass(status) {
  const statusMap = {
    'running': 'running',
    'completed': 'completed',
    'failed': 'failed',
    'error': 'failed',
    'pending': 'pending',
    'idle': 'idle',
    'waiting': 'pending',
    'queued': 'pending'
  };

  return statusMap[status?.toLowerCase()] || 'pending';
}

/**
 * Get status display text
 * @param {string} status - Agent status
 * @returns {string} Display text
 */
function getStatusText(status) {
  if (!status) return 'Unknown';
  return status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();
}

/**
 * Generate progress gradient based on progress and status
 * @param {number} progress - Progress percentage (0-100)
 * @param {string} status - Agent status
 * @returns {string} CSS gradient string
 */
function getProgressGradient(progress, status) {
  const colors = {
    'running': 'var(--color-running)',
    'completed': 'var(--color-success)',
    'failed': 'var(--color-error)',
    'pending': 'var(--color-pending)',
    'idle': 'var(--color-idle)'
  };

  const color = colors[status?.toLowerCase()] || 'var(--color-coral)';

  if (status === 'running') {
    return `linear-gradient(90deg, ${color} 0%, var(--color-coral-light) 100%)`;
  }

  return color;
}

/**
 * Generate a unique ID
 * @param {string} prefix - Optional prefix for the ID
 * @returns {string} Unique ID
 */
function generateId(prefix = 'id') {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Deep clone an object
 * @param {any} obj - Object to clone
 * @returns {any} Cloned object
 */
function deepClone(obj) {
  if (obj === null || typeof obj !== 'object') return obj;

  try {
    return JSON.parse(JSON.stringify(obj));
  } catch (e) {
    console.warn('Deep clone failed:', e);
    return obj;
  }
}

/**
 * Get nested object property safely
 * @param {object} obj - Object to access
 * @param {string} path - Dot-notation path
 * @param {any} defaultValue - Default value if not found
 * @returns {any} Property value or default
 */
function getNestedValue(obj, path, defaultValue = undefined) {
  if (!obj || !path) return defaultValue;

  return path.split('.').reduce((acc, part) => {
    return acc && acc[part] !== undefined ? acc[part] : defaultValue;
  }, obj);
}

/**
 * Group an array of objects by a key
 * @param {Array} array - Array to group
 * @param {string|Function} key - Key to group by or function to get key
 * @returns {object} Grouped object
 */
function groupBy(array, key) {
  if (!Array.isArray(array)) return {};

  return array.reduce((result, item) => {
    const groupKey = typeof key === 'function' ? key(item) : item[key];
    (result[groupKey] = result[groupKey] || []).push(item);
    return result;
  }, {});
}

/**
 * Sort array of objects by property
 * @param {Array} array - Array to sort
 * @param {string} key - Property key
 * @param {boolean} ascending - Sort order
 * @returns {Array} Sorted array
 */
function sortBy(array, key, ascending = true) {
  if (!Array.isArray(array)) return [];

  return [...array].sort((a, b) => {
    const valA = a[key];
    const valB = b[key];

    if (valA < valB) return ascending ? -1 : 1;
    if (valA > valB) return ascending ? 1 : -1;
    return 0;
  });
}

/**
 * Parse WebSocket message safely
 * @param {string} message - Message string
 * @returns {object|null} Parsed message or null
 */
function parseMessage(message) {
  try {
    return JSON.parse(message);
  } catch (e) {
    console.warn('Failed to parse message:', e);
    return null;
  }
}

/**
 * Format timestamp for display
 * @param {number|string|Date} timestamp - Timestamp to format
 * @returns {string} Formatted time string (HH:MM:SS)
 */
function formatTime(timestamp) {
  if (!timestamp) return '--:--:--';

  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

/**
 * Calculate ETA based on progress and elapsed time
 * @param {number} progress - Current progress (0-100)
 * @param {number|string|Date} startTime - Start timestamp
 * @returns {string} Formatted ETA string
 */
function calculateETA(progress, startTime) {
  if (!progress || progress <= 0 || !startTime) return '--:--';
  if (progress >= 100) return '0:00';

  const start = new Date(startTime);
  const now = new Date();
  const elapsed = now - start;
  const totalEstimate = (elapsed / progress) * 100;
  const remaining = totalEstimate - elapsed;

  return formatDuration(remaining);
}

/**
 * Create CSS class string from object
 * @param {object} classes - Object with class names as keys and booleans as values
 * @returns {string} Space-separated class string
 */
function classNames(classes) {
  return Object.entries(classes)
    .filter(([_, value]) => value)
    .map(([key]) => key)
    .join(' ');
}

/**
 * Store value in localStorage with JSON serialization
 * @param {string} key - Storage key
 * @param {any} value - Value to store
 */
function setStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    console.warn('Failed to set storage:', e);
  }
}

/**
 * Get value from localStorage with JSON parsing
 * @param {string} key - Storage key
 * @param {any} defaultValue - Default value if not found
 * @returns {any} Stored value or default
 */
function getStorage(key, defaultValue = null) {
  try {
    const item = localStorage.getItem(key);
    return item ? JSON.parse(item) : defaultValue;
  } catch (e) {
    console.warn('Failed to get storage:', e);
    return defaultValue;
  }
}

/**
 * Check if an element is in the viewport
 * @param {HTMLElement} element - Element to check
 * @returns {boolean} Whether element is visible
 */
function isInViewport(element) {
  if (!element) return false;

  const rect = element.getBoundingClientRect();
  return (
    rect.top >= 0 &&
    rect.left >= 0 &&
    rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
    rect.right <= (window.innerWidth || document.documentElement.clientWidth)
  );
}

/**
 * Truncate string to specified length with ellipsis
 * @param {string} str - String to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} Truncated string
 */
function truncate(str, maxLength = 50) {
  if (!str || str.length <= maxLength) return str || '';
  return str.substring(0, maxLength - 3) + '...';
}

// Export utilities for use in other modules
window.DashboardUtils = {
  formatTimeAgo,
  formatDuration,
  formatElapsed,
  formatNumber,
  formatPercentage,
  formatTime,
  debounce,
  throttle,
  escapeHtml,
  getStatusClass,
  getStatusBadgeClass,
  getStatusText,
  getProgressGradient,
  generateId,
  deepClone,
  getNestedValue,
  groupBy,
  sortBy,
  parseMessage,
  calculateETA,
  classNames,
  setStorage,
  getStorage,
  isInViewport,
  truncate
};
