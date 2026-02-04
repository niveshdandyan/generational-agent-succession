/**
 * GAS Dashboard - WebSocket Client
 * Real-time communication with the dashboard server
 */

class DashboardWebSocket {
  /**
   * Create a WebSocket client for the dashboard
   * @param {string} url - WebSocket server URL
   * @param {object} options - Configuration options
   */
  constructor(url, options = {}) {
    this.url = url;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
    this.reconnectDelay = options.reconnectDelay || 1000;
    this.maxReconnectDelay = options.maxReconnectDelay || 30000;
    this.heartbeatInterval = options.heartbeatInterval || 30000;
    this.listeners = new Map();
    this.messageQueue = [];
    this.isConnecting = false;
    this.heartbeatTimer = null;
    this.reconnectTimer = null;
    this.connectionState = 'disconnected';

    // Bind methods to preserve context
    this.handleOpen = this.handleOpen.bind(this);
    this.handleClose = this.handleClose.bind(this);
    this.handleError = this.handleError.bind(this);
    this.handleMessage = this.handleMessage.bind(this);
  }

  /**
   * Get current connection state
   * @returns {string} Connection state
   */
  get state() {
    return this.connectionState;
  }

  /**
   * Check if WebSocket is connected
   * @returns {boolean} Connection status
   */
  get isConnected() {
    return this.ws && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * Connect to the WebSocket server
   * @returns {Promise} Resolves when connected
   */
  connect() {
    return new Promise((resolve, reject) => {
      if (this.isConnected) {
        resolve();
        return;
      }

      if (this.isConnecting) {
        // Wait for existing connection attempt
        this.once('open', () => resolve());
        this.once('error', (error) => reject(error));
        return;
      }

      this.isConnecting = true;
      this.setConnectionState('connecting');

      try {
        this.ws = new WebSocket(this.url);

        // Set up event handlers
        this.ws.onopen = (event) => {
          this.handleOpen(event);
          resolve();
        };

        this.ws.onclose = this.handleClose;
        this.ws.onerror = (error) => {
          this.handleError(error);
          if (this.isConnecting) {
            reject(error);
          }
        };
        this.ws.onmessage = this.handleMessage;

      } catch (error) {
        this.isConnecting = false;
        this.setConnectionState('disconnected');
        reject(error);
      }
    });
  }

  /**
   * Disconnect from the WebSocket server
   */
  disconnect() {
    this.clearTimers();
    this.reconnectAttempts = this.maxReconnectAttempts; // Prevent auto-reconnect

    if (this.ws) {
      this.ws.onclose = null; // Prevent reconnect on intentional close
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.setConnectionState('disconnected');
    this.emit('disconnected');
  }

  /**
   * Handle WebSocket open event
   * @param {Event} event - Open event
   */
  handleOpen(event) {
    this.isConnecting = false;
    this.reconnectAttempts = 0;
    this.setConnectionState('connected');
    this.startHeartbeat();
    this.flushMessageQueue();
    this.emit('open', event);
    this.emit('connected');

    console.log('[WebSocket] Connected to', this.url);
  }

  /**
   * Handle WebSocket close event
   * @param {CloseEvent} event - Close event
   */
  handleClose(event) {
    this.isConnecting = false;
    this.clearTimers();
    this.setConnectionState('disconnected');
    this.emit('close', event);

    console.log('[WebSocket] Disconnected:', event.code, event.reason);

    // Attempt to reconnect if not a clean close
    if (event.code !== 1000) {
      this.scheduleReconnect();
    }
  }

  /**
   * Handle WebSocket error event
   * @param {Event} error - Error event
   */
  handleError(error) {
    console.error('[WebSocket] Error:', error);
    this.emit('error', error);
  }

  /**
   * Handle incoming WebSocket message
   * @param {MessageEvent} event - Message event
   */
  handleMessage(event) {
    const data = DashboardUtils.parseMessage(event.data);

    if (!data) {
      console.warn('[WebSocket] Failed to parse message:', event.data);
      return;
    }

    // Handle system messages
    if (data.type === 'pong') {
      this.emit('pong', data);
      return;
    }

    if (data.type === 'welcome') {
      console.log('[WebSocket] Server welcome:', data.message);
      this.emit('welcome', data);
      return;
    }

    // Emit typed events
    if (data.type) {
      this.emit(data.type, data.payload || data.data || data);
    }

    // Emit generic message event
    this.emit('message', data);
  }

  /**
   * Send a message to the server
   * @param {object} message - Message to send
   * @returns {boolean} Whether message was sent
   */
  send(message) {
    const data = typeof message === 'string' ? message : JSON.stringify(message);

    if (this.isConnected) {
      try {
        this.ws.send(data);
        return true;
      } catch (error) {
        console.error('[WebSocket] Send error:', error);
        this.messageQueue.push(data);
        return false;
      }
    } else {
      // Queue message for when connection is established
      this.messageQueue.push(data);
      return false;
    }
  }

  /**
   * Send a typed message
   * @param {string} type - Message type
   * @param {object} payload - Message payload
   * @returns {boolean} Whether message was sent
   */
  sendTyped(type, payload = {}) {
    return this.send({ type, payload, timestamp: Date.now() });
  }

  /**
   * Subscribe to an event
   * @param {string} event - Event name
   * @param {Function} callback - Event handler
   * @returns {Function} Unsubscribe function
   */
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event).add(callback);

    // Return unsubscribe function
    return () => this.off(event, callback);
  }

  /**
   * Subscribe to an event once
   * @param {string} event - Event name
   * @param {Function} callback - Event handler
   */
  once(event, callback) {
    const wrapper = (...args) => {
      this.off(event, wrapper);
      callback.apply(this, args);
    };
    this.on(event, wrapper);
  }

  /**
   * Unsubscribe from an event
   * @param {string} event - Event name
   * @param {Function} callback - Event handler
   */
  off(event, callback) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).delete(callback);
    }
  }

  /**
   * Emit an event to all listeners
   * @param {string} event - Event name
   * @param {any} data - Event data
   */
  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`[WebSocket] Error in ${event} handler:`, error);
        }
      });
    }
  }

  /**
   * Schedule a reconnection attempt
   */
  scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('[WebSocket] Max reconnect attempts reached');
      this.emit('reconnect_failed');
      return;
    }

    // Calculate delay with exponential backoff
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts),
      this.maxReconnectDelay
    );

    console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`);

    this.setConnectionState('reconnecting');
    this.emit('reconnecting', { attempt: this.reconnectAttempts + 1, delay });

    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect().catch(error => {
        console.error('[WebSocket] Reconnect failed:', error);
      });
    }, delay);
  }

  /**
   * Manually trigger a reconnection
   */
  reconnect() {
    this.disconnect();
    this.reconnectAttempts = 0;
    return this.connect();
  }

  /**
   * Start heartbeat ping to keep connection alive
   */
  startHeartbeat() {
    this.clearHeartbeat();

    this.heartbeatTimer = setInterval(() => {
      if (this.isConnected) {
        this.send({ type: 'ping', timestamp: Date.now() });
      }
    }, this.heartbeatInterval);
  }

  /**
   * Clear heartbeat timer
   */
  clearHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  /**
   * Clear all timers
   */
  clearTimers() {
    this.clearHeartbeat();

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  /**
   * Flush queued messages
   */
  flushMessageQueue() {
    while (this.messageQueue.length > 0 && this.isConnected) {
      const message = this.messageQueue.shift();
      try {
        this.ws.send(message);
      } catch (error) {
        console.error('[WebSocket] Failed to send queued message:', error);
        this.messageQueue.unshift(message);
        break;
      }
    }
  }

  /**
   * Update connection state and emit event
   * @param {string} state - New connection state
   */
  setConnectionState(state) {
    if (this.connectionState !== state) {
      this.connectionState = state;
      this.emit('state_change', state);
    }
  }

  /**
   * Request full status update from server
   */
  requestStatus() {
    this.sendTyped('request_status');
  }

  /**
   * Subscribe to agent events
   * @param {string} agentId - Agent ID to subscribe to
   */
  subscribeToAgent(agentId) {
    this.sendTyped('subscribe_agent', { agentId });
  }

  /**
   * Unsubscribe from agent events
   * @param {string} agentId - Agent ID to unsubscribe from
   */
  unsubscribeFromAgent(agentId) {
    this.sendTyped('unsubscribe_agent', { agentId });
  }
}

// Export for use in other modules
window.DashboardWebSocket = DashboardWebSocket;
