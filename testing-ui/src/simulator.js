/**
 * AAROGYA-SHIELD: Simulation Lab Controller
 * Controls sensor sliders, debounced API dispatch, presets,
 * step-up risk escalation, and gradual physiological recovery.
 */

import { api } from './api.js';

export const PRESETS = {
  normal: {
    heart_rate: 74,
    spo2: 98,
    ppg_quality: 0.96,
    body_temperature: 36.7,
    ambient_temperature: 28.0,
    humidity: 60,
    mq45: 180,
    accel_x: 0.02,
    accel_y: 0.01,
    accel_z: 0.98,
  },
  early_resp: {
    heart_rate: 84,
    spo2: 95,
    ppg_quality: 0.94,
    body_temperature: 37.0,
    ambient_temperature: 28.5,
    humidity: 60,
    mq45: 220,
    accel_x: 0.02,
    accel_y: 0.01,
    accel_z: 0.98,
  },
  resp_elev: {
    heart_rate: 98,
    spo2: 92,
    ppg_quality: 0.92,
    body_temperature: 37.4,
    ambient_temperature: 29.0,
    humidity: 62,
    mq45: 340,
    accel_x: 0.02,
    accel_y: 0.01,
    accel_z: 0.98,
  },
  heat: {
    heart_rate: 104,
    spo2: 97,
    ppg_quality: 0.93,
    body_temperature: 38.5,
    ambient_temperature: 38.0,
    humidity: 78,
    mq45: 210,
    accel_x: 0.04,
    accel_y: 0.03,
    accel_z: 1.02,
  },
  env: {
    heart_rate: 82,
    spo2: 96,
    ppg_quality: 0.94,
    body_temperature: 36.9,
    ambient_temperature: 32.0,
    humidity: 65,
    mq45: 580,
    accel_x: 0.02,
    accel_y: 0.01,
    accel_z: 0.98,
  },
  fatigue: {
    heart_rate: 118,
    spo2: 95,
    ppg_quality: 0.90,
    body_temperature: 37.8,
    ambient_temperature: 28.0,
    humidity: 60,
    mq45: 190,
    accel_x: 0.40,
    accel_y: 0.30,
    accel_z: 1.45,
  },
  critical: {
    heart_rate: 136,
    spo2: 85,
    ppg_quality: 0.88,
    body_temperature: 39.4,
    ambient_temperature: 35.0,
    humidity: 72,
    mq45: 680,
    accel_x: 0.02,
    accel_y: 0.01,
    accel_z: 0.98,
  },
  recovery: {
    heart_rate: 82,
    spo2: 97,
    ppg_quality: 0.95,
    body_temperature: 36.9,
    ambient_temperature: 28.0,
    humidity: 60,
    mq45: 180,
    accel_x: 0.02,
    accel_y: 0.01,
    accel_z: 0.98,
  },
};

export class SimulatorController {
  constructor(onReadingProcessed) {
    this.onReadingProcessed = onReadingProcessed;
    this.debounceTimer = null;
    this.isDispatching = false;
    this.stepIndex = 0;
    this.recoveryTimer = null;

    // Pairs of (number input ID, range input ID)
    this.controlPairs = [
      { num: 'num-hr', range: 'range-hr', key: 'heart_rate', parse: parseFloat },
      { num: 'num-spo2', range: 'range-spo2', key: 'spo2', parse: parseFloat },
      { num: 'num-ppg', range: 'range-ppg', key: 'ppg_quality', parse: parseFloat },
      { num: 'num-temp', range: 'range-temp', key: 'body_temperature', parse: parseFloat },
      { num: 'num-amb', range: 'range-amb', key: 'ambient_temperature', parse: parseFloat },
      { num: 'num-hum', range: 'range-hum', key: 'humidity', parse: parseFloat },
      { num: 'num-mq', range: 'range-mq', key: 'mq45', parse: parseFloat },
    ];

    this._bindControls();
    this._bindPresets();
    this._bindWorkflowButtons();
  }

  _bindControls() {
    this.controlPairs.forEach(({ num, range }) => {
      const numEl = document.getElementById(num);
      const rangeEl = document.getElementById(range);

      if (numEl && rangeEl) {
        // Slider movement updates numeric input
        rangeEl.addEventListener('input', () => {
          numEl.value = rangeEl.value;
          this._scheduleDebouncedDispatch();
        });

        // Numeric typing updates slider
        numEl.addEventListener('input', () => {
          rangeEl.value = numEl.value;
          this._scheduleDebouncedDispatch();
        });
      }
    });

    // Acceleration inputs
    ['num-ax', 'num-ay', 'num-az'].forEach((id) => {
      document.getElementById(id)?.addEventListener('input', () => {
        this._updateAccelMagnitudeLabel();
        this._scheduleDebouncedDispatch();
      });
    });

    // Activity Quick Buttons
    document.getElementById('btn-act-rest')?.addEventListener('click', () => {
      this._setAccel(0.02, 0.01, 0.98);
    });
    document.getElementById('btn-act-walk')?.addEventListener('click', () => {
      this._setAccel(0.25, 0.20, 1.25);
    });
    document.getElementById('btn-act-run')?.addEventListener('click', () => {
      this._setAccel(0.50, 0.40, 1.70);
    });
    document.getElementById('btn-act-fall')?.addEventListener('click', () => {
      this._setAccel(2.10, 1.80, 0.35); // Sudden impact fall candidate
    });

    // Device ID and GPS inputs
    ['txt-device-id', 'num-lat', 'num-lon'].forEach((id) => {
      document.getElementById(id)?.addEventListener('change', () => {
        this._scheduleDebouncedDispatch();
      });
    });
  }

  _setAccel(x, y, z) {
    const ax = document.getElementById('num-ax');
    const ay = document.getElementById('num-ay');
    const az = document.getElementById('num-az');
    if (ax) ax.value = x.toFixed(2);
    if (ay) ay.value = y.toFixed(2);
    if (az) az.value = z.toFixed(2);
    this._updateAccelMagnitudeLabel();
    this._scheduleDebouncedDispatch();
  }

  _updateAccelMagnitudeLabel() {
    const ax = parseFloat(document.getElementById('num-ax')?.value || 0.02);
    const ay = parseFloat(document.getElementById('num-ay')?.value || 0.01);
    const az = parseFloat(document.getElementById('num-az')?.value || 0.98);
    const mag = Math.sqrt(ax * ax + ay * ay + az * az).toFixed(2);
    const lbl = document.getElementById('lbl-accel-mag');
    if (lbl) lbl.textContent = `MAG: ${mag}g`;
  }

  _bindPresets() {
    document.querySelectorAll('.btn-preset').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const presetKey = e.currentTarget.getAttribute('data-preset');
        if (PRESETS[presetKey]) {
          this.applyValues(PRESETS[presetKey]);
          // Highlight active preset button
          document.querySelectorAll('.btn-preset').forEach((b) => b.classList.remove('active'));
          e.currentTarget.classList.add('active');
          // Immediately trigger real ML test
          this.executeInference();
        }
      });
    });
  }

  _bindWorkflowButtons() {
    // Primary RUN ML TEST button
    document.getElementById('btn-run-ml')?.addEventListener('click', () => {
      this.executeInference();
    });

    // STEP UP Button
    document.getElementById('btn-step-up')?.addEventListener('click', () => {
      this.stepUpRisk();
    });

    // RECOVER Button
    document.getElementById('btn-recover')?.addEventListener('click', () => {
      this.startRecoverySequence();
    });

    // START BASELINE
    document.getElementById('btn-start-baseline')?.addEventListener('click', async () => {
      const devId = document.getElementById('txt-device-id')?.value || 'SIM-001';
      const statusChip = document.getElementById('chip-inference-timing');
      try {
        if (statusChip) statusChip.textContent = 'CALIBRATING BASELINE...';
        await api.startBaseline(devId);
        // Feed current reading into baseline
        await this.executeInference();
        const baseState = document.getElementById('lbl-baseline-state');
        if (baseState) baseState.textContent = 'CALIBRATED';
      } catch (err) {
        console.error('Failed to calibrate baseline:', err);
      }
    });

    // RESET BASELINE
    document.getElementById('btn-reset-baseline')?.addEventListener('click', async () => {
      const devId = document.getElementById('txt-device-id')?.value || 'SIM-001';
      try {
        await api.startBaseline(devId);
        await this.executeInference();
        const baseState = document.getElementById('lbl-baseline-state');
        if (baseState) baseState.textContent = 'RESET ACTIVE';
      } catch (err) {
        console.error('Failed to reset baseline:', err);
      }
    });
  }

  _scheduleDebouncedDispatch() {
    clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => {
      this.executeInference();
    }, 120); // 120ms debounce
  }

  getPayload() {
    return {
      device_id: document.getElementById('txt-device-id')?.value || 'SIM-001',
      timestamp: new Date().toISOString(),
      heart_rate: parseFloat(document.getElementById('num-hr')?.value || 74),
      spo2: parseFloat(document.getElementById('num-spo2')?.value || 98),
      ppg_quality: parseFloat(document.getElementById('num-ppg')?.value || 0.96),
      body_temperature: parseFloat(document.getElementById('num-temp')?.value || 36.7),
      ambient_temperature: parseFloat(document.getElementById('num-amb')?.value || 28.0),
      humidity: parseFloat(document.getElementById('num-hum')?.value || 60),
      mq45: parseFloat(document.getElementById('num-mq')?.value || 180),
      accel_x: parseFloat(document.getElementById('num-ax')?.value || 0.02),
      accel_y: parseFloat(document.getElementById('num-ay')?.value || 0.01),
      accel_z: parseFloat(document.getElementById('num-az')?.value || 0.98),
      latitude: parseFloat(document.getElementById('num-lat')?.value || 10.662),
      longitude: parseFloat(document.getElementById('num-lon')?.value || 76.891),
      is_simulator: true,
    };
  }

  applyValues(values) {
    if (!values) return;
    this.controlPairs.forEach(({ num, range, key }) => {
      if (values[key] !== undefined) {
        const numEl = document.getElementById(num);
        const rangeEl = document.getElementById(range);
        if (numEl) numEl.value = values[key];
        if (rangeEl) rangeEl.value = values[key];
      }
    });

    if (values.accel_x !== undefined) document.getElementById('num-ax').value = values.accel_x;
    if (values.accel_y !== undefined) document.getElementById('num-ay').value = values.accel_y;
    if (values.accel_z !== undefined) document.getElementById('num-az').value = values.accel_z;
    this._updateAccelMagnitudeLabel();
  }

  async executeInference() {
    if (this.isDispatching) return;
    this.isDispatching = true;

    const runBtn = document.getElementById('btn-run-ml');
    const btnText = document.getElementById('btn-run-ml-text');
    const timingChip = document.getElementById('txt-inference-status');

    if (runBtn) runBtn.disabled = true;
    if (btnText) btnText.textContent = 'RUNNING INFERENCE...';

    const payload = this.getPayload();
    const startTime = performance.now();

    try {
      const response = await api.sendSimulatorReading(payload);
      const latency = Math.round(performance.now() - startTime);
      const timeStr = new Date().toLocaleTimeString();

      if (timingChip) {
        timingChip.textContent = `INFERENCE COMPLETE · ${latency} ms · ${timeStr}`;
      }

      // Notify parent app
      if (this.onReadingProcessed) {
        this.onReadingProcessed(response, latency);
      }

      return response;
    } catch (err) {
      if (timingChip) {
        timingChip.textContent = `INFERENCE FAILED · ${err.message}`;
      }
      console.error('[Simulator] Inference error:', err);
      throw err;
    } finally {
      this.isDispatching = false;
      if (runBtn) runBtn.disabled = false;
      if (btnText) btnText.textContent = 'RUN ML TEST';
    }
  }

  async stepUpRisk() {
    const steps = [
      PRESETS.normal,
      PRESETS.early_resp,
      PRESETS.resp_elev,
      PRESETS.heat,
      PRESETS.critical,
    ];

    this.stepIndex = (this.stepIndex + 1) % steps.length;
    this.applyValues(steps[this.stepIndex]);
    await this.executeInference();
  }

  async startRecoverySequence() {
    clearInterval(this.recoveryTimer);

    // Gradual decay sequence toward personal baseline
    const target = PRESETS.normal;
    let currentHR = parseFloat(document.getElementById('num-hr')?.value || 74);
    let currentSpO2 = parseFloat(document.getElementById('num-spo2')?.value || 98);
    let currentTemp = parseFloat(document.getElementById('num-temp')?.value || 36.7);
    let currentMQ = parseFloat(document.getElementById('num-mq')?.value || 180);

    const stepInterval = 400; // ms per step
    const totalSteps = 5;
    let stepCount = 0;

    const hrStep = (target.heart_rate - currentHR) / totalSteps;
    const spo2Step = (target.spo2 - currentSpO2) / totalSteps;
    const tempStep = (target.body_temperature - currentTemp) / totalSteps;
    const mqStep = (target.mq45 - currentMQ) / totalSteps;

    this.recoveryTimer = setInterval(async () => {
      stepCount++;
      currentHR += hrStep;
      currentSpO2 += spo2Step;
      currentTemp += tempStep;
      currentMQ += mqStep;

      this.applyValues({
        heart_rate: Math.round(currentHR),
        spo2: Math.round(currentSpO2),
        body_temperature: parseFloat(currentTemp.toFixed(1)),
        mq45: Math.round(currentMQ),
      });

      await this.executeInference();

      if (stepCount >= totalSteps) {
        clearInterval(this.recoveryTimer);
        this.applyValues(target);
        await this.executeInference();
      }
    }, stepInterval);
  }
}
