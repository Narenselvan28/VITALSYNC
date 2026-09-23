/**
 * AAROGYA-SHIELD: Centralized API Client
 * Interfaces with FastAPI backend on VITE_API_URL.
 * Thin client: No calculations, no fabricated risk.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export class ApiService {
  constructor() {
    this.baseUrl = API_BASE;
    this.lastRequest = null;
    this.lastResponse = null;
    this.lastLatencyMs = 0;
    this.lastEndpoint = '';
    this.lastStatus = 0;
    this.isOnline = true;
    this.listeners = [];
  }

  onTelemetryUpdate(listener) {
    this.listeners.push(listener);
  }

  notifyDebugUpdate() {
    this.listeners.forEach((fn) =>
      fn({
        endpoint: this.lastEndpoint,
        status: this.lastStatus,
        latencyMs: this.lastLatencyMs,
        request: this.lastRequest,
        response: this.lastResponse,
        isOnline: this.isOnline,
      })
    );
  }

  async _fetch(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    this.lastEndpoint = `${options.method || 'GET'} ${endpoint}`;
    const startTime = performance.now();

    try {
      const resp = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...(options.headers || {}),
        },
        ...options,
      });

      this.lastLatencyMs = Math.round(performance.now() - startTime);
      this.lastStatus = resp.status;
      this.isOnline = true;

      if (!resp.ok) {
        const errorText = await resp.text();
        this.lastResponse = { error: errorText, status: resp.status };
        this.notifyDebugUpdate();
        throw new Error(`HTTP ${resp.status}: ${errorText}`);
      }

      const data = await resp.json();
      this.lastResponse = data;
      this.notifyDebugUpdate();
      return data;
    } catch (err) {
      this.lastLatencyMs = Math.round(performance.now() - startTime);
      if (err.name === 'TypeError' && err.message.includes('fetch')) {
        this.isOnline = false;
      }
      this.lastResponse = { error: err.message };
      this.notifyDebugUpdate();
      throw err;
    }
  }

  async sendSimulatorReading(payload) {
    this.lastRequest = payload;
    return await this._fetch('/api/simulator/readings', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async fetchHealth() {
    return await this._fetch('/api/health');
  }

  async fetchDeviceStatus(deviceId = 'SIM-001') {
    return await this._fetch(`/api/device/status?device_id=${encodeURIComponent(deviceId)}`);
  }

  async fetchBaseline(deviceId = 'SIM-001') {
    return await this._fetch(`/api/baseline?device_id=${encodeURIComponent(deviceId)}`);
  }

  async startBaseline(deviceId = 'SIM-001') {
    this.lastRequest = { device_id: deviceId };
    return await this._fetch('/api/baseline/start', {
      method: 'POST',
      body: JSON.stringify({ device_id: deviceId }),
    });
  }

  async fetchLatestAlert() {
    return await this._fetch('/api/alerts/latest');
  }

  async fetchAlerts(limit = 20) {
    return await this._fetch(`/api/alerts?limit=${limit}`);
  }

  async acknowledgeAlert(alertId) {
    this.lastRequest = { alert_id: alertId };
    return await this._fetch(`/api/alerts/${encodeURIComponent(alertId)}/acknowledge`, {
      method: 'POST',
    });
  }
}

export const api = new ApiService();
