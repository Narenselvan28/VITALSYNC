import { api, API_BASE } from './api.js';

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
    mq45: 180,
    accel_x: 0.02,
    accel_y: 0.01,
    accel_z: 0.98,
  },
  exercise: {
    heart_rate: 150,
    spo2: 97,
    ppg_quality: 0.94,
    body_temperature: 37.6,
    ambient_temperature: 28.0,
    humidity: 60,
    mq45: 180,
    accel_x: 0.45,
    accel_y: 0.35,
    accel_z: 1.60,
  },
  hr_spike: {
    heart_rate: 198,
    spo2: 96,
    ppg_quality: 0.93,
    body_temperature: 37.1,
    ambient_temperature: 28.0,
    humidity: 60,
    mq45: 180,
    accel_x: 0.04,
    accel_y: 0.02,
    accel_z: 1.00,
  },
  tachycardia: {
    heart_rate: 125,
    spo2: 97,
    ppg_quality: 0.94,
    body_temperature: 37.0,
    ambient_temperature: 28.0,
    humidity: 60,
    mq45: 180,
    accel_x: 0.02,
    accel_y: 0.01,
    accel_z: 0.98,
  },
  ntc_beverage: {
    heart_rate: 76,
    spo2: 98,
    ppg_quality: 0.95,
    body_temperature: 41.2,
    ambient_temperature: 28.0,
    humidity: 60,
    mq45: 180,
    accel_x: 0.02,
    accel_y: 0.01,
    accel_z: 0.98,
  },
  gas_exposure: {
    heart_rate: 88,
    spo2: 95,
    ppg_quality: 0.92,
    body_temperature: 37.0,
    ambient_temperature: 30.0,
    humidity: 68,
    mq45: 780,
    accel_x: 0.02,
    accel_y: 0.01,
    accel_z: 0.98,
  }
};

export class SimulatorController {
  constructor(onReadingProcessed) {
    this.onReadingProcessed = onReadingProcessed;
    this.sourceMode = 'SIMULATOR';
    this.isDispatching = false;
    this.debounceTimer = null;
    this.recoveryTimer = null;
    this.stepIndex = 0;
    this.packetCount = 0;

    this.controlPairs = [
      { num: 'num-hr', range: 'range-hr', key: 'heart_rate' },
      { num: 'num-spo2', range: 'range-spo2', key: 'spo2' },
      { num: 'num-ppg', range: 'range-ppg', key: 'ppg_quality' },
      { num: 'num-temp', range: 'range-temp', key: 'body_temperature' },
      { num: 'num-amb', range: 'range-amb', key: 'ambient_temperature' },
      { num: 'num-hum', range: 'range-hum', key: 'humidity' },
      { num: 'num-mq', range: 'range-mq', key: 'mq45' },
    ];

    this.initSourceToggle();
    this.bindControls();
    this.bindPresets();
    this.bindWorkflowButtons();
  }

  initSourceToggle() {
    const btnSim = document.getElementById('btn-src-sim');
    const btnReal = document.getElementById('btn-src-real');
    const dotSim = document.getElementById('dot-src-sim');
    const dotReal = document.getElementById('dot-src-real');
    const banner = document.getElementById('real-sensors-banner');
    const controlsSec = document.querySelector('.sliders-grid');
    const liveLbl = document.getElementById('lbl-simulator-live');
    const devIdInput = document.getElementById('txt-device-id');

    btnSim?.addEventListener('click', () => {
      this.sourceMode = 'SIMULATOR';
      btnSim.classList.add('active');
      btnReal?.classList.remove('active');
      if (dotSim) dotSim.className = 'dot dot-success';
      if (dotReal) dotReal.className = 'dot dot-muted';
      banner?.classList.add('hidden');
      controlsSec?.classList.remove('hw-locked');
      if (liveLbl) liveLbl.textContent = 'Simulator active';
      if (devIdInput) devIdInput.value = 'SIM-001';
      this.executeInference();
    });

    btnReal?.addEventListener('click', () => {
      this.sourceMode = 'REAL';
      btnReal.classList.add('active');
      btnSim?.classList.remove('active');
      if (dotReal) dotReal.className = 'dot dot-success';
      if (dotSim) dotSim.className = 'dot dot-muted';
      banner?.classList.remove('hidden');
      controlsSec?.classList.add('hw-locked');
      if (liveLbl) liveLbl.textContent = 'Hardware active';
      if (devIdInput) devIdInput.value = 'ESP32-001';
      this.pingHardwareEndpoint();
    });

    document.getElementById('btn-hw-ping')?.addEventListener('click', () => {
      this.pingHardwareEndpoint();
    });
  }

  async pingHardwareEndpoint() {
    const payload = {
      device_id: 'ESP32-001',
      timestamp: new Date().toISOString(),
      heart_rate: 74 + Math.round((Math.random() - 0.5) * 4),
      spo2: 98 + Math.round((Math.random() - 0.5) * 1),
      ppg_quality: 0.96,
      body_temperature: 36.75,
      ambient_temperature: 28.4,
      humidity: 61,
      accel_x: 0.02,
      accel_y: 0.01,
      accel_z: 0.98,
      mq45: 180,
      latitude: 10.662,
      longitude: 76.891,
      is_simulator: false,
    };

    try {
      const res = await fetch(`${API_BASE}/api/sensors/readings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const data = await res.json();
        this.updateHardwareTelemetry(data);
        if (this.onReadingProcessed) {
          this.onReadingProcessed(data, 25);
        }
      }
    } catch (e) {
      console.warn('Hardware ping failed:', e);
    }
  }

  updateHardwareTelemetry(payload) {
    if (!payload) return;
    this.packetCount = payload.packets_received || (this.packetCount + 1);

    const pktLbl = document.getElementById('lbl-hw-packets');
    if (pktLbl) pktLbl.textContent = `${this.packetCount} packets · 1 Hz`;

    const raw = payload.raw_sensors || payload.sensor_data || {};
    const features = payload.features || {};

    const ppgEl = document.getElementById('lbl-hw-ppg');
    if (ppgEl) {
      const q = Math.round((raw.ppg_quality || features.ppg_quality || 0.95) * 100);
      ppgEl.textContent = `Finger detected (${q}%)`;
    }

    const motionEl = document.getElementById('lbl-hw-motion');
    if (motionEl) {
      const mag = (features.acceleration_magnitude || 0.98).toFixed(2);
      const act = features.activity_level || 'Rest';
      motionEl.textContent = `${mag} g (${act.toLowerCase()})`;
    }

    const dhtEl = document.getElementById('lbl-hw-dht');
    if (dhtEl) {
      const amb = (raw.ambient_temperature || 28.0).toFixed(1);
      const hum = Math.round(raw.humidity || 60);
      dhtEl.textContent = `${amb}°C / ${hum}%`;
    }

    const mqEl = document.getElementById('lbl-hw-mq');
    if (mqEl) {
      const mq = Math.round(raw.mq45 || 180);
      const status = mq > 400 ? 'Elevated' : 'Nominal';
      mqEl.textContent = `${mq} (${status})`;
    }

    if (this.sourceMode === 'REAL') {
      this.applyValues(raw);
    }
  }

  bindControls() {
    this.controlPairs.forEach(({ num, range }) => {
      const numEl = document.getElementById(num);
      const rangeEl = document.getElementById(range);

      if (numEl && rangeEl) {
        rangeEl.addEventListener('input', () => {
          numEl.value = rangeEl.value;
          this.scheduleDebouncedDispatch();
        });

        numEl.addEventListener('input', () => {
          rangeEl.value = numEl.value;
          this.scheduleDebouncedDispatch();
        });
      }
    });

    ['num-ax', 'num-ay', 'num-az'].forEach((id) => {
      document.getElementById(id)?.addEventListener('input', () => {
        this.updateAccelMagnitudeLabel();
        this.scheduleDebouncedDispatch();
      });
    });

    document.getElementById('btn-act-rest')?.addEventListener('click', () => this.setAccel(0.02, 0.01, 0.98));
    document.getElementById('btn-act-walk')?.addEventListener('click', () => this.setAccel(0.25, 0.20, 1.25));
    document.getElementById('btn-act-run')?.addEventListener('click', () => this.setAccel(0.50, 0.40, 1.70));
    document.getElementById('btn-act-fall')?.addEventListener('click', () => this.setAccel(2.10, 1.80, 0.35));

    ['txt-device-id', 'num-lat', 'num-lon'].forEach((id) => {
      document.getElementById(id)?.addEventListener('change', () => {
        this.scheduleDebouncedDispatch();
      });
    });
  }

  setAccel(x, y, z) {
    const ax = document.getElementById('num-ax');
    const ay = document.getElementById('num-ay');
    const az = document.getElementById('num-az');
    if (ax) ax.value = x.toFixed(2);
    if (ay) ay.value = y.toFixed(2);
    if (az) az.value = z.toFixed(2);
    this.updateAccelMagnitudeLabel();
    this.scheduleDebouncedDispatch();
  }

  updateAccelMagnitudeLabel() {
    const ax = parseFloat(document.getElementById('num-ax')?.value || 0.02);
    const ay = parseFloat(document.getElementById('num-ay')?.value || 0.01);
    const az = parseFloat(document.getElementById('num-az')?.value || 0.98);
    const mag = Math.sqrt(ax * ax + ay * ay + az * az).toFixed(2);
    const lbl = document.getElementById('lbl-accel-mag');
    if (lbl) lbl.textContent = `${mag} g`;
  }

  bindPresets() {
    document.querySelectorAll('.btn-preset').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const presetKey = e.currentTarget.getAttribute('data-preset');
        if (PRESETS[presetKey]) {
          this.applyValues(PRESETS[presetKey]);
          document.querySelectorAll('.btn-preset').forEach((b) => b.classList.remove('active'));
          e.currentTarget.classList.add('active');
          this.executeInference();
        }
      });
    });
  }

  bindWorkflowButtons() {
    document.getElementById('btn-run-ml')?.addEventListener('click', () => {
      this.executeInference();
    });

    document.getElementById('btn-step-up')?.addEventListener('click', () => {
      this.stepUpRisk();
    });

    document.getElementById('btn-recover')?.addEventListener('click', () => {
      this.startRecoverySequence();
    });

    document.getElementById('btn-start-baseline')?.addEventListener('click', async () => {
      const devId = document.getElementById('txt-device-id')?.value || 'SIM-001';
      const statusChip = document.getElementById('txt-inference-status');
      try {
        if (statusChip) statusChip.textContent = 'Calibrating baseline...';
        await api.startBaseline(devId);
        await this.executeInference();
        const baseState = document.getElementById('lbl-baseline-state');
        if (baseState) baseState.textContent = 'Calibrated';
      } catch (err) {
        console.error('Failed to calibrate baseline:', err);
      }
    });

    document.getElementById('btn-reset-baseline')?.addEventListener('click', async () => {
      const devId = document.getElementById('txt-device-id')?.value || 'SIM-001';
      try {
        await api.startBaseline(devId);
        await this.executeInference();
        const baseState = document.getElementById('lbl-baseline-state');
        if (baseState) baseState.textContent = 'Reset';
      } catch (err) {
        console.error('Failed to reset baseline:', err);
      }
    });
  }

  scheduleDebouncedDispatch() {
    clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => {
      this.executeInference();
    }, 120);
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
    this.updateAccelMagnitudeLabel();
  }

  async executeInference() {
    if (this.isDispatching) return;
    this.isDispatching = true;

    const runBtn = document.getElementById('btn-run-ml');
    const btnText = document.getElementById('btn-run-ml-text');
    const timingChip = document.getElementById('txt-inference-status');

    if (runBtn) runBtn.disabled = true;
    if (btnText) btnText.textContent = 'Running...';

    const payload = this.getPayload();
    const startTime = performance.now();

    try {
      const response = await api.sendSimulatorReading(payload);
      const latency = Math.round(performance.now() - startTime);

      if (timingChip) {
        timingChip.textContent = `Completed in ${latency} ms`;
      }

      if (this.onReadingProcessed) {
        this.onReadingProcessed(response, latency);
      }

      return response;
    } catch (err) {
      if (timingChip) {
        timingChip.textContent = `Failed: ${err.message}`;
      }
      console.error('Inference error:', err);
      throw err;
    } finally {
      this.isDispatching = false;
      if (runBtn) runBtn.disabled = false;
      if (btnText) btnText.textContent = 'Run inference';
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

    const target = PRESETS.normal;
    let currentHR = parseFloat(document.getElementById('num-hr')?.value || 74);
    let currentSpO2 = parseFloat(document.getElementById('num-spo2')?.value || 98);
    let currentTemp = parseFloat(document.getElementById('num-temp')?.value || 36.7);
    let currentMQ = parseFloat(document.getElementById('num-mq')?.value || 180);

    const stepInterval = 400;
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
