import { api } from './api.js';
import { wsClient } from './websocket.js';
import { SmartwatchController } from './smartwatch.js';
import { SimulatorController } from './simulator.js';
import { MLPanelController } from './ml_panel.js';
import { CaretakerAlertController } from './caretaker.js';
import { TimelineController } from './timeline.js';
import { DebugPanelController } from './debug_panel.js';
import { TestRunnerController } from './test_runner.js';
import { ProfileController } from './profile_controller.js';

class VitalSyncApp {
  constructor() {
    this.lastSequenceId = -1;
    this.smartwatch = new SmartwatchController();
    this.mlPanel = new MLPanelController();
    this.timeline = new TimelineController(300);
    this.debugPanel = new DebugPanelController();

    this.profile = new ProfileController(async () => {
      try {
        await this.simulator.executeInference();
      } catch (e) {
        console.warn('Re-inference error:', e);
      }
    });

    this.caretaker = new CaretakerAlertController(() => {
      this.refreshLatestAlert();
    });

    this.simulator = new SimulatorController((response, latencyMs) => {
      this.handleUnifiedTelemetry(response, latencyMs);
    });

    this.testRunner = new TestRunnerController(this.simulator, (response, latencyMs) => {
      this.handleUnifiedTelemetry(response, latencyMs);
    });

    this.bindSystemEvents();
    this.init();
  }

  async init() {
    await this.checkBackendHealth();
    await this.fetchInitialBaseline();
    await this.profile.loadInitialProfile();
    wsClient.connect();

    try {
      await this.simulator.executeInference();
    } catch {
      // Default initial view
    }
  }

  bindSystemEvents() {
    wsClient.onMessage((msg) => {
      if (msg.event_type === 'TELEMETRY_UPDATE') {
        this.handleUnifiedTelemetry(msg, 0);
        if (msg.origin === 'IOT' || !msg.raw_sensors?.is_simulator) {
          this.simulator.updateHardwareTelemetry(msg);
        }
      } else if (msg.event_type === 'PROFILE_UPDATED') {
        this.profile.updateDisplay({
          patient_profile: msg.profile,
          active_condition_contexts: msg.active_contexts || [],
        });
      } else if (msg.event_type === 'ALERT_ACKNOWLEDGED') {
        this.caretaker.updateDisplay(null);
      }
    });

    wsClient.onStatusChange((status) => {
      const pillWs = document.getElementById('lbl-ws');
      const dotWs = document.getElementById('dot-ws');
      if (pillWs) pillWs.textContent = status === 'CONNECTED' ? 'Live' : 'Offline';
      if (dotWs) dotWs.className = 'dot ' + (status === 'CONNECTED' ? 'dot-success' : 'dot-danger');
      this.debugPanel.updateWsStatus(status);
    });

    api.onTelemetryUpdate((telemetry) => {
      this.debugPanel.updateFromTelemetry(telemetry);
      this.setBackendOnline(telemetry.isOnline);
    });

    document.getElementById('btn-reconnect')?.addEventListener('click', async () => {
      await this.checkBackendHealth();
      wsClient.connect();
    });
  }

  handleUnifiedTelemetry(payload, latencyMs = 0) {
    if (!payload) return;

    if (payload.sequence_id !== undefined) {
      if (payload.sequence_id <= this.lastSequenceId) return;
      this.lastSequenceId = payload.sequence_id;
    }

    this.smartwatch.updateDisplay(payload, latencyMs);
    this.mlPanel.updateDisplay(payload);
    this.caretaker.updateDisplay(payload.active_alert || payload.alert);
    this.timeline.addEntryFromPayload(payload);
    this.profile.updateDisplay(payload);
  }

  async checkBackendHealth() {
    try {
      const health = await api.fetchHealth();
      this.setBackendOnline(true);

      const mlLbl = document.getElementById('lbl-ml');
      const mlDot = document.getElementById('dot-ml');
      if (health.models_loaded) {
        if (mlLbl) mlLbl.textContent = 'Active';
        if (mlDot) mlDot.className = 'dot dot-success';
      } else {
        if (mlLbl) mlLbl.textContent = 'Fallback';
        if (mlDot) mlDot.className = 'dot dot-warning';
      }
    } catch {
      this.setBackendOnline(false);
    }
  }

  async fetchInitialBaseline() {
    try {
      const data = await api.fetchBaseline('SIM-001');
      if (data && data.statistics) {
        this.timeline.updateBaselineSummary(data.statistics);
      }
    } catch {
      // Nominal fallback
    }
  }

  async refreshLatestAlert() {
    try {
      const alert = await api.fetchLatestAlert('SIM-001');
      this.caretaker.updateDisplay(alert);
    } catch {
      // Ignored
    }
  }

  setBackendOnline(isOnline) {
    const banner = document.getElementById('offline-banner');
    const lblBackend = document.getElementById('lbl-backend');
    const dotBackend = document.getElementById('dot-backend');

    if (banner) banner.classList.toggle('hidden', isOnline);
    if (lblBackend) lblBackend.textContent = isOnline ? 'Connected' : 'Offline';
    if (dotBackend) dotBackend.className = 'dot ' + (isOnline ? 'dot-success' : 'dot-danger');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.vitalSyncApp = new VitalSyncApp();
});
