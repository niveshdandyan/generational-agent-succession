/**
 * GAS Dashboard - UI Components
 * Rendering functions for dashboard UI elements
 */

const Components = {
  /**
   * Render the stats bar with agent counts
   * @param {object} data - Stats data { total, running, completed, failed, pending }
   */
  renderStatsBar(data) {
    const stats = {
      total: data.total || 0,
      running: data.running || 0,
      completed: data.completed || 0,
      failed: data.failed || 0,
      pending: data.pending || 0
    };

    document.getElementById('stat-total').textContent = stats.total;
    document.getElementById('stat-running').textContent = stats.running;
    document.getElementById('stat-completed').textContent = stats.completed;
    document.getElementById('stat-failed').textContent = stats.failed;
    document.getElementById('stat-pending').textContent = stats.pending;
  },

  /**
   * Render the progress section
   * @param {object} data - Progress data { progress, startTime, eta }
   */
  renderProgressSection(data) {
    const progress = data.progress || 0;
    const startTime = data.startTime;

    // Update percentage
    const percentageEl = document.getElementById('progress-percentage');
    percentageEl.textContent = `${Math.round(progress)}%`;

    // Update progress bar
    const progressFill = document.querySelector('.progress-fill');
    progressFill.style.width = `${progress}%`;

    // Update elapsed time
    const elapsedEl = document.getElementById('progress-elapsed');
    elapsedEl.textContent = `Elapsed: ${DashboardUtils.formatElapsed(startTime)}`;

    // Update ETA
    const etaEl = document.getElementById('progress-eta');
    etaEl.textContent = `ETA: ${DashboardUtils.calculateETA(progress, startTime)}`;
  },

  /**
   * Render an agent card
   * @param {object} agent - Agent data
   * @returns {string} HTML string
   */
  renderAgentCard(agent) {
    const statusClass = DashboardUtils.getStatusClass(agent.status);
    const badgeClass = DashboardUtils.getStatusBadgeClass(agent.status);
    const progress = agent.progress || 0;
    const tools = agent.tools || {};

    // Generate tool badges HTML
    const toolBadges = Object.entries(tools)
      .slice(0, 4)
      .map(([tool, count]) => this.renderToolBadge(tool, count))
      .join('');

    const moreTools = Object.keys(tools).length > 4
      ? `<span class="tool-badge">+${Object.keys(tools).length - 4}</span>`
      : '';

    return `
      <div class="agent-card ${statusClass}" data-agent-id="${DashboardUtils.escapeHtml(agent.id)}" tabindex="0">
        <div class="agent-card-header">
          <div>
            <div class="agent-name">${DashboardUtils.escapeHtml(agent.name || agent.id)}</div>
            <div class="agent-id">${DashboardUtils.escapeHtml(agent.id)}</div>
          </div>
          ${this.renderStatusBadge(agent.status)}
        </div>
        <div class="agent-role">${DashboardUtils.escapeHtml(agent.role || 'Agent')}</div>
        <div class="agent-progress">
          <div class="agent-progress-fill" style="width: ${progress}%"></div>
        </div>
        <div class="agent-meta">
          <span>${DashboardUtils.formatTimeAgo(agent.lastActivity || agent.updatedAt)}</span>
          <span>${Math.round(progress)}%</span>
        </div>
        ${toolBadges || moreTools ? `<div class="agent-tools">${toolBadges}${moreTools}</div>` : ''}
      </div>
    `;
  },

  /**
   * Render a status badge
   * @param {string} status - Agent status
   * @returns {string} HTML string
   */
  renderStatusBadge(status) {
    const badgeClass = DashboardUtils.getStatusBadgeClass(status);
    const statusText = DashboardUtils.getStatusText(status);

    return `
      <span class="status-badge ${badgeClass}">
        <span class="status-indicator"></span>
        ${DashboardUtils.escapeHtml(statusText)}
      </span>
    `;
  },

  /**
   * Render a tool badge
   * @param {string} tool - Tool name
   * @param {number} count - Usage count
   * @returns {string} HTML string
   */
  renderToolBadge(tool, count) {
    const shortName = tool.length > 12 ? tool.substring(0, 10) + '...' : tool;
    return `<span class="tool-badge" title="${DashboardUtils.escapeHtml(tool)}">${DashboardUtils.escapeHtml(shortName)}: ${count}</span>`;
  },

  /**
   * Render a wave group
   * @param {string} waveId - Wave identifier
   * @param {Array} agents - Agents in this wave
   * @param {object} waveInfo - Wave metadata
   * @returns {string} HTML string
   */
  renderWaveGroup(waveId, agents, waveInfo = {}) {
    const waveNum = waveId.replace('wave-', '').replace('wave', '');
    const completed = agents.filter(a => a.status === 'completed').length;
    const total = agents.length;

    const agentCards = agents
      .sort((a, b) => {
        // Sort by status priority: running > pending > completed > failed
        const priority = { running: 0, pending: 1, completed: 2, failed: 3 };
        return (priority[a.status] || 4) - (priority[b.status] || 4);
      })
      .map(agent => this.renderAgentCard(agent))
      .join('');

    return `
      <div class="wave-group" data-wave-id="${DashboardUtils.escapeHtml(waveId)}">
        <div class="wave-header">
          <h3 class="wave-title">Wave ${DashboardUtils.escapeHtml(waveNum)}</h3>
          <span class="wave-badge">${completed}/${total} completed</span>
        </div>
        <div class="wave-agents">
          ${agentCards}
        </div>
      </div>
    `;
  },

  /**
   * Render the full agents grid grouped by waves
   * @param {object} agents - Agents keyed by ID
   * @param {object} waves - Wave configuration
   */
  renderAgentsGrid(agents, waves = {}) {
    const grid = document.getElementById('agents-grid');

    if (!agents || Object.keys(agents).length === 0) {
      grid.innerHTML = `
        <div class="loading-placeholder">
          <div class="loading-spinner"></div>
          <p>Waiting for agent data...</p>
        </div>
      `;
      return;
    }

    // Group agents by wave
    const agentList = Object.values(agents);
    const grouped = DashboardUtils.groupBy(agentList, agent => agent.wave || 'wave-1');

    // Sort waves by wave number
    const sortedWaves = Object.keys(grouped).sort((a, b) => {
      const numA = parseInt(a.replace(/\D/g, '')) || 0;
      const numB = parseInt(b.replace(/\D/g, '')) || 0;
      return numA - numB;
    });

    // Render wave groups
    const html = sortedWaves
      .map(waveId => this.renderWaveGroup(waveId, grouped[waveId], waves[waveId]))
      .join('');

    grid.innerHTML = html;

    // Add click handlers to agent cards
    grid.querySelectorAll('.agent-card').forEach(card => {
      card.addEventListener('click', () => {
        const agentId = card.dataset.agentId;
        if (window.app && window.app.selectAgent) {
          window.app.selectAgent(agentId);
        }
      });

      // Keyboard accessibility
      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          card.click();
        }
      });
    });
  },

  /**
   * Update a single agent card without full re-render
   * @param {object} agent - Updated agent data
   */
  updateAgentCard(agent) {
    const card = document.querySelector(`.agent-card[data-agent-id="${agent.id}"]`);

    if (!card) {
      // Agent not in grid, might need full re-render
      return false;
    }

    // Update status class
    const statusClass = DashboardUtils.getStatusClass(agent.status);
    card.className = `agent-card ${statusClass}`;

    // Update progress
    const progressFill = card.querySelector('.agent-progress-fill');
    if (progressFill) {
      progressFill.style.width = `${agent.progress || 0}%`;
    }

    // Update status badge
    const badgeContainer = card.querySelector('.agent-card-header');
    const existingBadge = card.querySelector('.status-badge');
    if (existingBadge) {
      existingBadge.outerHTML = this.renderStatusBadge(agent.status);
    }

    // Update meta
    const metaEl = card.querySelector('.agent-meta');
    if (metaEl) {
      metaEl.innerHTML = `
        <span>${DashboardUtils.formatTimeAgo(agent.lastActivity || agent.updatedAt)}</span>
        <span>${Math.round(agent.progress || 0)}%</span>
      `;
    }

    return true;
  },

  /**
   * Render the detail panel for an agent
   * @param {object} agent - Agent data
   */
  renderDetailPanel(agent) {
    const panel = document.getElementById('detail-panel');
    const overlay = document.getElementById('detail-overlay');
    const titleEl = document.getElementById('detail-title');
    const contentEl = document.getElementById('detail-content');

    if (!agent) {
      panel.classList.remove('active');
      overlay.classList.remove('active');
      return;
    }

    titleEl.textContent = agent.name || agent.id;

    // Build tool usage section
    const tools = agent.tools || {};
    const toolsHtml = Object.entries(tools)
      .map(([tool, count]) => `
        <div class="detail-tool-badge">
          <span>${DashboardUtils.escapeHtml(tool)}</span>
          <span class="detail-tool-count">${count}</span>
        </div>
      `)
      .join('') || '<p class="text-muted">No tools used yet</p>';

    // Build events section
    const events = agent.events || [];
    const eventsHtml = events.slice(-10).reverse()
      .map(event => this.renderDetailEvent(event))
      .join('') || '<p class="text-muted">No events recorded</p>';

    // Build output section
    const output = agent.output || agent.lastOutput || '';
    const outputHtml = output
      ? `<pre class="detail-output">${DashboardUtils.escapeHtml(output)}</pre>`
      : '<p class="text-muted">No output available</p>';

    contentEl.innerHTML = `
      <div class="detail-section">
        <h3 class="detail-section-title">Information</h3>
        <div class="detail-info-grid">
          <div class="detail-info-item">
            <span class="detail-info-label">ID</span>
            <span class="detail-info-value">${DashboardUtils.escapeHtml(agent.id)}</span>
          </div>
          <div class="detail-info-item">
            <span class="detail-info-label">Status</span>
            <span class="detail-info-value">${this.renderStatusBadge(agent.status)}</span>
          </div>
          <div class="detail-info-item">
            <span class="detail-info-label">Wave</span>
            <span class="detail-info-value">${DashboardUtils.escapeHtml(agent.wave || 'N/A')}</span>
          </div>
          <div class="detail-info-item">
            <span class="detail-info-label">Progress</span>
            <span class="detail-info-value">${Math.round(agent.progress || 0)}%</span>
          </div>
          <div class="detail-info-item">
            <span class="detail-info-label">Started</span>
            <span class="detail-info-value">${DashboardUtils.formatTime(agent.startedAt)}</span>
          </div>
          <div class="detail-info-item">
            <span class="detail-info-label">Duration</span>
            <span class="detail-info-value">${DashboardUtils.formatElapsed(agent.startedAt)}</span>
          </div>
        </div>
      </div>

      <div class="detail-section">
        <h3 class="detail-section-title">Role & Mission</h3>
        <p>${DashboardUtils.escapeHtml(agent.role || 'No role specified')}</p>
        ${agent.mission ? `<p class="text-muted">${DashboardUtils.escapeHtml(agent.mission)}</p>` : ''}
      </div>

      <div class="detail-section">
        <h3 class="detail-section-title">Tool Usage</h3>
        <div class="detail-tools-grid">
          ${toolsHtml}
        </div>
      </div>

      <div class="detail-section">
        <h3 class="detail-section-title">Recent Events</h3>
        <div class="detail-events-list">
          ${eventsHtml}
        </div>
      </div>

      <div class="detail-section">
        <h3 class="detail-section-title">Output</h3>
        ${outputHtml}
      </div>
    `;

    // Show panel
    panel.classList.add('active');
    overlay.classList.add('active');
  },

  /**
   * Render a detail event item
   * @param {object} event - Event data
   * @returns {string} HTML string
   */
  renderDetailEvent(event) {
    const typeClass = event.type === 'error' ? 'error'
      : event.type === 'tool' ? 'tool-call'
      : 'status-change';

    return `
      <div class="detail-event ${typeClass}">
        <span class="event-time">${DashboardUtils.formatTime(event.timestamp)}</span>
        <span class="event-content">${DashboardUtils.escapeHtml(event.message || event.type)}</span>
      </div>
    `;
  },

  /**
   * Render a live event in the feed
   * @param {object} event - Event data
   * @returns {string} HTML string
   */
  renderLiveEvent(event) {
    const eventType = event.type || 'status';
    const typeClass = `event-${eventType}`;

    return `
      <div class="event-item ${typeClass}">
        <div class="event-time">${DashboardUtils.formatTime(event.timestamp || Date.now())}</div>
        <div>
          <span class="event-agent">${DashboardUtils.escapeHtml(event.agentId || event.agent || 'System')}</span>
          <span class="event-content">${DashboardUtils.escapeHtml(event.message || event.data || '')}</span>
        </div>
      </div>
    `;
  },

  /**
   * Add a live event to the feed
   * @param {object} event - Event data
   */
  addLiveEvent(event) {
    const feed = document.getElementById('events-feed');
    const placeholder = feed.querySelector('.event-placeholder');

    // Remove placeholder if present
    if (placeholder) {
      placeholder.remove();
    }

    // Create event element
    const eventHtml = this.renderLiveEvent(event);
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = eventHtml;
    const eventEl = tempDiv.firstElementChild;

    // Add to top of feed
    feed.insertBefore(eventEl, feed.firstChild);

    // Limit feed to 100 events
    while (feed.children.length > 100) {
      feed.removeChild(feed.lastChild);
    }
  },

  /**
   * Clear the live events feed
   */
  clearLiveEvents() {
    const feed = document.getElementById('events-feed');
    feed.innerHTML = `
      <div class="event-placeholder">
        <p>Waiting for events...</p>
      </div>
    `;
  },

  /**
   * Update WebSocket status indicator
   * @param {string} state - Connection state
   */
  updateWsStatus(state) {
    const statusEl = document.getElementById('ws-status');
    const textEl = statusEl.querySelector('.ws-text');

    // Remove all state classes
    statusEl.classList.remove('connected', 'disconnected', 'connecting', 'reconnecting');

    // Add appropriate class and text
    switch (state) {
      case 'connected':
        statusEl.classList.add('connected');
        textEl.textContent = 'Connected';
        break;
      case 'disconnected':
        statusEl.classList.add('disconnected');
        textEl.textContent = 'Disconnected';
        break;
      case 'connecting':
        statusEl.classList.add('connecting');
        textEl.textContent = 'Connecting...';
        break;
      case 'reconnecting':
        statusEl.classList.add('connecting');
        textEl.textContent = 'Reconnecting...';
        break;
      default:
        statusEl.classList.add('disconnected');
        textEl.textContent = 'Unknown';
    }
  },

  /**
   * Show/hide loading state
   * @param {boolean} isLoading - Whether loading
   */
  setLoading(isLoading) {
    const grid = document.getElementById('agents-grid');

    if (isLoading && (!grid.children.length || grid.querySelector('.loading-placeholder'))) {
      grid.innerHTML = `
        <div class="loading-placeholder">
          <div class="loading-spinner"></div>
          <p>Loading dashboard data...</p>
        </div>
      `;
    }
  }
};

// Export for use in other modules
window.Components = Components;
