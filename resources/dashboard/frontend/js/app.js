/**
 * GAS Dashboard - Main Application
 * Orchestrates the dashboard functionality with WebSocket real-time updates
 */

const app = {
  // WebSocket client
  ws: null,

  // Application state
  state: {
    agents: {},
    waves: {},
    selectedAgent: null,
    filter: 'all',
    theme: 'light',
    startTime: null,
    isLoading: true
  },

  // Timers for periodic updates
  timers: {
    elapsed: null
  },

  /**
   * Initialize the application
   */
  init() {
    console.log('[App] Initializing GAS Dashboard v2.0');

    // Initialize theme
    this.initTheme();

    // Initialize WebSocket connection
    this.initWebSocket();

    // Bind event handlers
    this.bindEvents();

    // Start periodic updates
    this.startPeriodicUpdates();

    // Set loading state
    Components.setLoading(true);

    console.log('[App] Initialization complete');
  },

  /**
   * Initialize theme from storage or system preference
   */
  initTheme() {
    // Check stored preference
    let theme = DashboardUtils.getStorage('dashboard-theme');

    // Fall back to system preference
    if (!theme) {
      theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    this.setTheme(theme);

    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      if (!DashboardUtils.getStorage('dashboard-theme')) {
        this.setTheme(e.matches ? 'dark' : 'light');
      }
    });
  },

  /**
   * Set the application theme
   * @param {string} theme - Theme name ('light' or 'dark')
   */
  setTheme(theme) {
    this.state.theme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    DashboardUtils.setStorage('dashboard-theme', theme);
  },

  /**
   * Toggle between light and dark themes
   */
  toggleTheme() {
    const newTheme = this.state.theme === 'light' ? 'dark' : 'light';
    this.setTheme(newTheme);
  },

  /**
   * Initialize WebSocket connection
   */
  initWebSocket() {
    // Determine WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    console.log('[App] Connecting to WebSocket:', wsUrl);

    // Create WebSocket client
    this.ws = new DashboardWebSocket(wsUrl, {
      maxReconnectAttempts: 10,
      reconnectDelay: 1000,
      heartbeatInterval: 30000
    });

    // Set up event handlers
    this.ws.on('state_change', this.handleConnectionStateChange.bind(this));
    this.ws.on('connected', this.handleConnected.bind(this));
    this.ws.on('disconnected', this.handleDisconnected.bind(this));

    // Handle incoming data events
    this.ws.on('status_update', this.handleStatusUpdate.bind(this));
    this.ws.on('full_status', this.handleFullStatus.bind(this));
    this.ws.on('live_event', this.handleLiveEvent.bind(this));
    this.ws.on('agent_update', this.handleAgentUpdate.bind(this));
    this.ws.on('wave_complete', this.handleWaveComplete.bind(this));

    // Handle errors
    this.ws.on('error', this.handleWebSocketError.bind(this));
    this.ws.on('reconnect_failed', this.handleReconnectFailed.bind(this));

    // Connect
    this.ws.connect().catch(error => {
      console.error('[App] Initial connection failed:', error);
    });
  },

  /**
   * Handle WebSocket connection state changes
   * @param {string} state - New connection state
   */
  handleConnectionStateChange(state) {
    Components.updateWsStatus(state);
  },

  /**
   * Handle successful WebSocket connection
   */
  handleConnected() {
    console.log('[App] WebSocket connected');

    // Request full status update
    this.ws.requestStatus();

    // Add connection event to live feed
    Components.addLiveEvent({
      type: 'status',
      message: 'Dashboard connected to server',
      timestamp: Date.now()
    });
  },

  /**
   * Handle WebSocket disconnection
   */
  handleDisconnected() {
    console.log('[App] WebSocket disconnected');

    Components.addLiveEvent({
      type: 'error',
      message: 'Lost connection to server',
      timestamp: Date.now()
    });
  },

  /**
   * Handle full status update from server
   * @param {object} data - Full status data
   */
  handleFullStatus(data) {
    console.log('[App] Received full status update');

    this.state.isLoading = false;

    // Update agents
    if (data.agents) {
      this.state.agents = data.agents;
    }

    // Update waves
    if (data.waves) {
      this.state.waves = data.waves;
    }

    // Update start time
    if (data.startTime) {
      this.state.startTime = data.startTime;
    }

    // Full re-render
    this.render();
  },

  /**
   * Handle incremental status update
   * @param {object} data - Status update data
   */
  handleStatusUpdate(data) {
    // Merge agents data
    if (data.agents) {
      Object.entries(data.agents).forEach(([id, agentData]) => {
        this.state.agents[id] = {
          ...this.state.agents[id],
          ...agentData
        };
      });
    }

    // Update start time if provided
    if (data.startTime && !this.state.startTime) {
      this.state.startTime = data.startTime;
    }

    // Re-render
    this.render();
  },

  /**
   * Handle individual agent update
   * @param {object} data - Agent update data
   */
  handleAgentUpdate(data) {
    if (!data || !data.id) return;

    // Update agent in state
    this.state.agents[data.id] = {
      ...this.state.agents[data.id],
      ...data
    };

    // Try to update just the card
    const updated = Components.updateAgentCard(this.state.agents[data.id]);

    if (!updated) {
      // Card doesn't exist, need full re-render
      this.renderAgents();
    }

    // Update stats and progress
    this.renderStats();
    this.renderProgress();

    // If this agent is selected, update detail panel
    if (this.state.selectedAgent === data.id) {
      Components.renderDetailPanel(this.state.agents[data.id]);
    }
  },

  /**
   * Handle live event from server
   * @param {object} event - Event data
   */
  handleLiveEvent(event) {
    Components.addLiveEvent(event);

    // If event is for selected agent, update detail panel
    if (event.agentId && event.agentId === this.state.selectedAgent) {
      const agent = this.state.agents[event.agentId];
      if (agent) {
        // Add event to agent's events
        if (!agent.events) agent.events = [];
        agent.events.push(event);
        Components.renderDetailPanel(agent);
      }
    }
  },

  /**
   * Handle wave completion event
   * @param {object} data - Wave completion data
   */
  handleWaveComplete(data) {
    Components.addLiveEvent({
      type: 'complete',
      message: `Wave ${data.waveId || data.wave} completed`,
      timestamp: Date.now()
    });

    // Re-render to show updated wave status
    this.renderAgents();
  },

  /**
   * Handle WebSocket error
   * @param {Error} error - Error object
   */
  handleWebSocketError(error) {
    console.error('[App] WebSocket error:', error);

    Components.addLiveEvent({
      type: 'error',
      message: 'Connection error occurred',
      timestamp: Date.now()
    });
  },

  /**
   * Handle reconnection failure
   */
  handleReconnectFailed() {
    console.error('[App] Failed to reconnect after maximum attempts');

    Components.addLiveEvent({
      type: 'error',
      message: 'Failed to reconnect to server. Please refresh the page.',
      timestamp: Date.now()
    });
  },

  /**
   * Bind DOM event handlers
   */
  bindEvents() {
    // Theme toggle
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', () => this.toggleTheme());
    }

    // Detail panel close
    const detailClose = document.getElementById('detail-close');
    const detailOverlay = document.getElementById('detail-overlay');

    if (detailClose) {
      detailClose.addEventListener('click', () => this.closeDetailPanel());
    }

    if (detailOverlay) {
      detailOverlay.addEventListener('click', () => this.closeDetailPanel());
    }

    // Escape key to close panel
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.state.selectedAgent) {
        this.closeDetailPanel();
      }
    });

    // Filter buttons
    const filterBtns = document.querySelectorAll('.filter-btn');
    filterBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const filter = btn.dataset.filter;
        this.setFilter(filter);
      });
    });

    // Clear events button
    const clearEventsBtn = document.getElementById('clear-events');
    if (clearEventsBtn) {
      clearEventsBtn.addEventListener('click', () => Components.clearLiveEvents());
    }

    // Handle visibility change to pause/resume updates
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        this.pausePeriodicUpdates();
      } else {
        this.startPeriodicUpdates();
        // Request fresh status when becoming visible
        if (this.ws && this.ws.isConnected) {
          this.ws.requestStatus();
        }
      }
    });
  },

  /**
   * Select an agent and show detail panel
   * @param {string} agentId - Agent ID
   */
  selectAgent(agentId) {
    this.state.selectedAgent = agentId;
    const agent = this.state.agents[agentId];

    if (agent) {
      Components.renderDetailPanel(agent);

      // Subscribe to agent-specific events
      if (this.ws && this.ws.isConnected) {
        this.ws.subscribeToAgent(agentId);
      }
    }
  },

  /**
   * Close the detail panel
   */
  closeDetailPanel() {
    const previousAgent = this.state.selectedAgent;
    this.state.selectedAgent = null;
    Components.renderDetailPanel(null);

    // Unsubscribe from agent events
    if (previousAgent && this.ws && this.ws.isConnected) {
      this.ws.unsubscribeFromAgent(previousAgent);
    }
  },

  /**
   * Set the current filter
   * @param {string} filter - Filter name
   */
  setFilter(filter) {
    this.state.filter = filter;

    // Update button states
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.filter === filter);
    });

    // Re-render agents with filter
    this.renderAgents();
  },

  /**
   * Start periodic UI updates
   */
  startPeriodicUpdates() {
    // Update elapsed time every second
    if (!this.timers.elapsed) {
      this.timers.elapsed = setInterval(() => {
        this.updateElapsedTime();
      }, 1000);
    }
  },

  /**
   * Pause periodic updates
   */
  pausePeriodicUpdates() {
    if (this.timers.elapsed) {
      clearInterval(this.timers.elapsed);
      this.timers.elapsed = null;
    }
  },

  /**
   * Update elapsed time display
   */
  updateElapsedTime() {
    if (this.state.startTime) {
      const elapsedEl = document.getElementById('progress-elapsed');
      if (elapsedEl) {
        elapsedEl.textContent = `Elapsed: ${DashboardUtils.formatElapsed(this.state.startTime)}`;
      }
    }
  },

  /**
   * Calculate statistics from agents
   * @returns {object} Stats object
   */
  calculateStats() {
    const agents = Object.values(this.state.agents);

    return {
      total: agents.length,
      running: agents.filter(a => a.status === 'running').length,
      completed: agents.filter(a => a.status === 'completed').length,
      failed: agents.filter(a => a.status === 'failed' || a.status === 'error').length,
      pending: agents.filter(a => a.status === 'pending' || a.status === 'idle' || a.status === 'waiting').length
    };
  },

  /**
   * Calculate overall progress
   * @returns {number} Progress percentage (0-100)
   */
  calculateProgress() {
    const agents = Object.values(this.state.agents);
    if (agents.length === 0) return 0;

    const completed = agents.filter(a => a.status === 'completed').length;
    return (completed / agents.length) * 100;
  },

  /**
   * Filter agents based on current filter
   * @returns {object} Filtered agents
   */
  getFilteredAgents() {
    if (this.state.filter === 'all') {
      return this.state.agents;
    }

    return Object.fromEntries(
      Object.entries(this.state.agents).filter(([_, agent]) => {
        switch (this.state.filter) {
          case 'running':
            return agent.status === 'running';
          case 'completed':
            return agent.status === 'completed';
          case 'failed':
            return agent.status === 'failed' || agent.status === 'error';
          default:
            return true;
        }
      })
    );
  },

  /**
   * Render the stats bar
   */
  renderStats() {
    const stats = this.calculateStats();
    Components.renderStatsBar(stats);
  },

  /**
   * Render the progress section
   */
  renderProgress() {
    const progress = this.calculateProgress();
    Components.renderProgressSection({
      progress,
      startTime: this.state.startTime
    });
  },

  /**
   * Render the agents grid
   */
  renderAgents() {
    const filteredAgents = this.getFilteredAgents();
    Components.renderAgentsGrid(filteredAgents, this.state.waves);
  },

  /**
   * Full render of all components
   */
  render() {
    this.renderStats();
    this.renderProgress();
    this.renderAgents();
  }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  app.init();
});

// Expose app globally for debugging and component access
window.app = app;
