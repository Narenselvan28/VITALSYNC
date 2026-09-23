/**
 * AAROGYA-SHIELD: Application Entry Point & Orchestrator
 * Bootstraps all controllers, live WebSocket stream,
 * and handles resilient state updates between Simulator, ML, and Smartwatch.
 */

import { api } from './api.js';
import { wsClient } from './websocket.js';
import { SmartwatchController } from './smartwatch.js';
import { SimulatorController } from './simulator.js';
import { MLPanelController } from './ml_panel.js';
import { CaretakerAlertController } from './caretaker.js';
import { TimelineController } from './timeline.js';
import { DebugPanelController } from './debug_panel.js';
import { TestRunnerController } from './test_runner.js';

class AarogyaShieldApp {
  constructor() {
    this.smartwatch = new SmartwatchController();
    this.mlPanel = new MLPanelController();
    this.timeline = new TimelineController(300);
    this.debugPanel = new DebugPanelController();

    this.caretaker = new CaretakerAlertController(() => {
      // Alert acknowledged: refresh alert and timeline
      this.refreshLatestAlert();
    });

    this.simulator = new SimulatorController((response, latencyMs) => {
      // Direct API response from simulator
      this.handleUnifiedTelemetry(response, latencyMs);
    });

    this.testRunner = new TestRunnerController(this.simulator, (response, latencyMs) => {
      this.handleUnifiedTelemetry(response, latencyMs);
    });

    this._bindSystemEvents();
    this.init();
  }

  async init() {
    // 1. Initial Health & Diagnostics check
    await this.checkBackendHealth();

    // 2. Fetch Initial Baseline
    await this.fetchInitialBaseline();

    // 3. Connect Live WebSocket
    wsClient.connect();

    // 4. Initial simulator dry run to seed initial dashboard values
    try {
      await this.simulator.executeInference();
    } catch (e) {
      console.warn('[App] Initial simulator inference skipped:', e.message);
    }
  }

  _bindSystemEvents() {
    // Listen for WebSocket Live Messages
    wsClient.onMessage((msg) => {
      if (msg.event_type === 'TELEMETRY_UPDATE') {
        this.handleUnifiedTelemetry(msg, 0);
      } else if (msg.event_type === 'ALERT_ACKNOWLEDGED') {
        this.caretaker.updateDisplay(null);
      }
    });

    // Listen for WebSocket Connection State
    wsClient.onStatusChange((status) => {
      const pillWs = document.getElementById('lbl-ws');
      const dotWs = document.getElementById('dot-ws');
      if (pillWs) pillWs.textContent = status === 'CONNECTED' ? 'LIVE' : 'DISCONNECTED';
      if (dotWs) dotWs.className = 'status-dot ' + (status === 'CONNECTED' ? 'green' : 'red');
      this.debugPanel.updateWsStatus(status);
    });

    // Listen for API Telemetry updates (Latency, request/response JSON)
    api.onTelemetryUpdate((telemetry) => {
      this.debugPanel.updateFromTelemetry(telemetry);
      this._setBackendOnline(telemetry.isOnline);
    });

    // Retry Reconnect Button
    document.getElementById('btn-reconnect')?.addEventListener('click', async () => {
      await this.checkBackendHealth();
      wsClient.connect();
    });
  }

  handleUnifiedTelemetry(payload, latencyMs = 0) {
    if (!payload) return;

    // Update all UI views directly from backend payload
    this.smartwatch.updateDisplay(payload, latencyMs);
    this.mlPanel.updateDisplay(payload);
    this.caretaker.updateDisplay(payload.active_alert || payload.alert);
    this.timeline.addEntryFromPayload(payload);
  }

  async checkBackendHealth() {
    try {
      const health = await api.fetchHealth();
      this._setBackendOnline(true);

      const mlLbl = document.getElementById('lbl-ml');
      const mlDot = document.getElementById('dot-ml');
      if (health.models_loaded) {
        if (mlLbl) mlLbl.textContent = 'XGBOOST v1';
        if (mlDot) mlDot.className = 'status-dot green';
      } else {
        if (mlLbl) mlLbl.textContent = 'DEV FALLBACK';
        if (mlDot) mlDot.className = 'status-dot amber';
      }

      // Check device status
      const devStatus = await api.fetchDeviceStatus('SIM-001');
      const espStatusEl = document.getElementById('w-sys-esp');
      if (espStatusEl) {
        if (devStatus.is_online) {
          espStatusEl.textContent = '● CONNECTED';
          espStatusEl.className = 'text-green';
        } else {
          espStatusEl.textContent = '○ SIMULATOR';
          espStatusEl.className = 'text-amber';
        }
      }
    } catch (err) {
      console.warn('[App] Health check failed, backend offline:', err.message);
      this._setBackendOnline(false);
    }
  }

  async fetchInitialBaseline() {
    try {
      const baseline = await api.fetchBaseline('SIM-001');
      if (baseline && baseline.statistics) {
        this.timeline.updateBaselineSummary(baseline.statistics);
      }
    } catch (err) {
      console.warn('[App] Baseline fetch error:', err.message);
    }
  }

  async refreshLatestAlert() {
    try {
      const alert = await api.fetchLatestAlert();
      this.caretaker.updateDisplay(alert);
    } catch (err) {
      console.warn('[App] Alert refresh error:', err.message);
    }
  }

  _setBackendOnline(isOnline) {
    const banner = document.getElementById('offline-banner');
    const lblBackend = document.getElementById('lbl-backend');
    const dotBackend = document.getElementById('dot-backend');

    if (banner) {
      banner.classList.toggle('hidden', isOnline);
    }
    if (lblBackend) {
      lblBackend.textContent = isOnline ? 'CONNECTED' : 'OFFLINE';
    }
    if (dotBackend) {
      dotBackend.className = 'status-dot ' + (isOnline ? 'green' : 'red');
    }
  }
}

// Bootstrap on DOM Content Loaded
document.addEventListener('DOMContentLoaded', () => {
  window.app = new AarogyaShieldApp();
});
