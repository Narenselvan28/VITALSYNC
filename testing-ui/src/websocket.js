/**
 * VITALSYNC: Live WebSocket Stream Client
 * Manages resilient bidirectional connection to /ws/live.
 * Supports auto-reconnect and state change notifications.
 */

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/live';

export class WebSocketClient {
  constructor(url = WS_URL) {
    this.url = url;
    this.socket = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectDelay = 10000;
    this.reconnectTimer = null;
    this.messageListeners = [];
    this.statusListeners = [];
    this.isManualClosed = false;
  }

  connect() {
    this.isManualClosed = false;
    if (this.socket && (this.socket.readyState === WebSocket.CONNECTING || this.socket.readyState === WebSocket.OPEN)) {
      return;
    }

    try {
      this.socket = new WebSocket(this.url);

      this.socket.onopen = () => {
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this._notifyStatus('CONNECTED');
      };

      this.socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this._notifyMessage(data);
        } catch (err) {
          console.warn('[WS] Failed to parse message JSON:', err);
        }
      };

      this.socket.onclose = () => {
        this.isConnected = false;
        this._notifyStatus('DISCONNECTED');
        if (!this.isManualClosed) {
          this._scheduleReconnect();
        }
      };

      this.socket.onerror = (err) => {
        this.isConnected = false;
        this._notifyStatus('DISCONNECTED');
      };
    } catch (err) {
      this.isConnected = false;
      this._notifyStatus('DISCONNECTED');
      this._scheduleReconnect();
    }
  }

  _scheduleReconnect() {
    clearTimeout(this.reconnectTimer);
    const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), this.maxReconnectDelay);
    this.reconnectAttempts++;
    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  disconnect() {
    this.isManualClosed = true;
    clearTimeout(this.reconnectTimer);
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.isConnected = false;
    this._notifyStatus('DISCONNECTED');
  }

  send(data) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      const msg = typeof data === 'string' ? data : JSON.stringify(data);
      this.socket.send(msg);
    }
  }

  onMessage(listener) {
    this.messageListeners.push(listener);
  }

  onStatusChange(listener) {
    this.statusListeners.push(listener);
    // Send immediate initial status
    listener(this.isConnected ? 'CONNECTED' : 'DISCONNECTED');
  }

  _notifyMessage(data) {
    this.messageListeners.forEach((fn) => fn(data));
  }

  _notifyStatus(status) {
    this.statusListeners.forEach((fn) => fn(status));
  }
}

export const wsClient = new WebSocketClient();
