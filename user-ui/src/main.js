const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/live';

class AarogyaCompanion {
  constructor() {
    this.ws = null;
    this.reconnectTimer = null;
    this.lastSequenceId = -1;
    this.activeSpikeDismissed = false;
    this.activeCriticalDismissed = false;

    this.cacheDom();
    this.bindEvents();
    this.startClock();
    this.init();
  }

  cacheDom() {
    this.clockEl = document.getElementById('watchTime');
    this.dateEl = document.getElementById('watchDate');
    this.monitoringPill = document.getElementById('monitoringPill');
    this.statusLabel = document.getElementById('statusLabel');
    this.statusPulseDot = document.getElementById('statusPulseDot');
    this.seqTag = document.getElementById('seqTag');

    this.valHR = document.getElementById('valHR');
    this.subHR = document.getElementById('subHR');
    this.valSpO2 = document.getElementById('valSpO2');
    this.subSpO2 = document.getElementById('subSpO2');
    this.valTemp = document.getElementById('valTemp');
    this.subTemp = document.getElementById('subTemp');
    this.valActivity = document.getElementById('valActivity');

    this.riskCard = document.getElementById('riskCard');
    this.riskBadge = document.getElementById('riskBadge');
    this.riskSummary = document.getElementById('riskSummary');
    this.riskDecisionSources = document.getElementById('riskDecisionSources');
    this.rdsList = document.getElementById('rdsList');
    this.riskProfileNotice = document.getElementById('riskProfileNotice');

    this.btnOpenProfile = document.getElementById('btnOpenProfile');
    this.profileStatusBar = document.getElementById('profileStatusBar');
    this.psbDot = document.getElementById('psbDot');
    this.psbTitle = document.getElementById('psbTitle');
    this.psbVersion = document.getElementById('psbVersion');
    this.psbHR = document.getElementById('psbHR');
    this.psbSpO2 = document.getElementById('psbSpO2');
    this.psbTemp = document.getElementById('psbTemp');
    this.psbAct = document.getElementById('psbAct');
    this.psbContextTags = document.getElementById('psbContextTags');

    this.profileModal = document.getElementById('profileModal');
    this.btnCloseProfile = document.getElementById('btnCloseProfile');
    this.profileForm = document.getElementById('profileForm');
    this.profAge = document.getElementById('profAge');
    this.profSex = document.getElementById('profSex');
    this.profHeight = document.getElementById('profHeight');
    this.profWeight = document.getElementById('profWeight');
    this.profMedications = document.getElementById('profMedications');
    this.condCheckboxes = document.querySelectorAll('input[name="condition"]');

    this.envAmbient = document.getElementById('envAmbient');
    this.envAir = document.getElementById('envAir');
    this.envGPS = document.getElementById('envGPS');

    this.spikeModal = document.getElementById('spikeAlertModal');
    this.spikeVitalName = document.getElementById('spikeVitalName');
    this.spikeVal = document.getElementById('spikeVal');
    this.spikeHeadline = document.getElementById('spikeHeadline');
    this.spikeSubline = document.getElementById('spikeSubline');
    this.btnDismissSpike = document.getElementById('btnDismissSpike');

    this.recoveredModal = document.getElementById('recoveredAlertModal');
    this.recoveredVal = document.getElementById('recoveredVal');
    this.btnDismissRecovered = document.getElementById('btnDismissRecovered');

    this.criticalModal = document.getElementById('criticalAlertModal');
    this.criticalHeadline = document.getElementById('criticalHeadline');
    this.criticalReason = document.getElementById('criticalReason');
    this.btnCheckUser = document.getElementById('btnCheckUser');

    this.wsSyncDot = document.getElementById('wsSyncDot');
    this.wsSyncText = document.getElementById('wsSyncText');
  }

  bindEvents() {
    this.btnOpenProfile?.addEventListener('click', () => this.profileModal?.classList.remove('hidden'));
    this.btnCloseProfile?.addEventListener('click', () => this.profileModal?.classList.add('hidden'));

    this.condCheckboxes.forEach((cb) => {
      cb.addEventListener('change', (e) => {
        const val = e.target.value;
        if ((val === 'none' || val === 'prefer_not_to_say') && e.target.checked) {
          this.condCheckboxes.forEach((other) => {
            if (other.value !== val) other.checked = false;
          });
        } else if (e.target.checked) {
          const noneCb = document.getElementById('cond-none');
          const preferNotCb = document.getElementById('cond-prefer-not');
          if (noneCb) noneCb.checked = false;
          if (preferNotCb) preferNotCb.checked = false;
        }
      });
    });

    this.profileForm?.addEventListener('submit', async (e) => {
      e.preventDefault();
      await this.saveProfile();
    });

    this.btnDismissSpike?.addEventListener('click', () => {
      this.spikeModal?.classList.add('hidden');
      this.activeSpikeDismissed = true;
    });

    this.btnDismissRecovered?.addEventListener('click', () => {
      this.recoveredModal?.classList.add('hidden');
    });

    this.btnCheckUser?.addEventListener('click', async () => {
      this.criticalModal?.classList.add('hidden');
      this.activeCriticalDismissed = true;
      try {
        await fetch(`${API_BASE}/api/alerts/latest`);
      } catch (e) {
        console.warn('Alert ack error:', e);
      }
    });

    document.getElementById('crownBtn')?.addEventListener('click', () => {
      this.activeSpikeDismissed = false;
      this.activeCriticalDismissed = false;
    });
  }

  startClock() {
    const tick = () => {
      const now = new Date();
      if (this.clockEl) {
        this.clockEl.textContent = now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
      }
      if (this.dateEl) {
        const days = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
        const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
        this.dateEl.textContent = `${days[now.getDay()]} ${now.getDate()} ${months[now.getMonth()]}`;
      }
    };
    tick();
    setInterval(tick, 1000);
  }

  async init() {
    await this.fetchInitialState();
    await this.fetchProfile();
    this.connectWebSocket();
  }

  async fetchProfile() {
    try {
      const resp = await fetch(`${API_BASE}/api/profile?device_id=ESP32-001`);
      if (!resp.ok) return;
      const data = await resp.json();
      const p = data.profile || {};
      if (this.profAge && p.age) this.profAge.value = p.age;
      if (this.profSex && p.sex) this.profSex.value = p.sex;
      if (this.profHeight && p.height_cm) this.profHeight.value = p.height_cm;
      if (this.profWeight && p.weight_kg) this.profWeight.value = p.weight_kg;
      if (this.profMedications && p.medication_context && p.medication_context !== 'UNKNOWN') {
        this.profMedications.value = p.medication_context;
      }
      const conditions = p.conditions || ['none'];
      this.condCheckboxes.forEach((cb) => {
        cb.checked = conditions.includes(cb.value);
      });
      if (!localStorage.getItem('aarogya_profile_completed')) {
        this.profileModal?.classList.remove('hidden');
      }
    } catch (e) {
      console.warn('Profile fetch skipped:', e);
    }
  }

  async saveProfile() {
    const age = parseInt(this.profAge?.value || "45", 10);
    const sex = this.profSex?.value || "Prefer not to say";
    const height_cm = parseFloat(this.profHeight?.value || "170");
    const weight_kg = parseFloat(this.profWeight?.value || "72");
    const medText = (this.profMedications?.value || "").trim();

    const selectedConditions = [];
    this.condCheckboxes.forEach((cb) => {
      if (cb.checked) selectedConditions.push(cb.value);
    });
    if (selectedConditions.length === 0) selectedConditions.push('none');

    const payload = {
      device_id: 'ESP32-001',
      age,
      sex,
      height_cm,
      weight_kg,
      conditions: selectedConditions,
      medications: medText ? [medText] : [],
      medication_context: medText || "UNKNOWN"
    };

    try {
      const resp = await fetch(`${API_BASE}/api/profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (resp.ok) {
        localStorage.setItem('aarogya_profile_completed', 'true');
        this.profileModal?.classList.add('hidden');
      }
    } catch (e) {
      console.error('Failed to save profile:', e);
    }
  }

  async fetchInitialState() {
    try {
      const resp = await fetch(`${API_BASE}/api/sensors/latest?device_id=ESP32-001`);
      if (!resp.ok) return;
      const data = await resp.json();
      this.renderState({
        sequence_id: 1,
        vitals: {
          heart_rate: data.heart_rate,
          spo2: data.spo2,
          temperature: data.body_temperature,
          ambient_temperature: data.ambient_temperature,
        },
        activity: { state: "Rest", intensity: 1.0 },
        environment: { raw_mq45: data.mq45 },
        gps: { lat: data.latitude, lon: data.longitude, valid: true },
        risk: { overall_score: 0.08, overall_level: "LOW" },
      });
    } catch {
      // Leave empty state dashes if initial fetch fails
    }
  }

  connectWebSocket() {
    clearTimeout(this.reconnectTimer);
    try {
      this.ws = new WebSocket(WS_URL);

      this.ws.onopen = () => {
        if (this.wsSyncDot) this.wsSyncDot.className = "dot dot-success";
        if (this.wsSyncText) this.wsSyncText.textContent = "Connected";
        if (this.statusLabel) this.statusLabel.textContent = "Monitoring";
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          this.handleUpdate(msg);
        } catch (e) {
          console.warn('WS parse error:', e);
        }
      };

      this.ws.onclose = () => {
        if (this.wsSyncDot) this.wsSyncDot.className = "dot dot-danger";
        if (this.wsSyncText) this.wsSyncText.textContent = "Reconnecting...";
        if (this.statusLabel) this.statusLabel.textContent = "Offline";
        this.reconnectTimer = setTimeout(() => this.connectWebSocket(), 2000);
      };

      this.ws.onerror = () => {
        if (this.wsSyncDot) this.wsSyncDot.className = "dot dot-danger";
      };
    } catch {
      this.reconnectTimer = setTimeout(() => this.connectWebSocket(), 2500);
    }
  }

  handleUpdate(msg) {
    if (!msg) return;

    if (msg.event_type === 'PROFILE_UPDATED') {
      const p = msg.profile || {};
      if (this.profAge && p.age) this.profAge.value = p.age;
      if (this.profSex && p.sex) this.profSex.value = p.sex;
      if (this.profHeight && p.height_cm) this.profHeight.value = p.height_cm;
      if (this.profWeight && p.weight_kg) this.profWeight.value = p.weight_kg;
      if (this.profMedications && p.medication_context && p.medication_context !== 'UNKNOWN') {
        this.profMedications.value = p.medication_context;
      }
      this.renderProfileBar({
        patient_profile: p,
        active_condition_contexts: msg.active_contexts || [],
        features: { baseline_summary: {} }
      });
      return;
    }

    if (msg.sequence_id !== undefined) {
      if (msg.sequence_id <= this.lastSequenceId) return;
      this.lastSequenceId = msg.sequence_id;
    }

    this.renderState(msg);
  }

  renderState(state) {
    const vitals = state.vitals || {};
    const activity = state.activity || {};
    const env = state.environment || {};
    const gps = state.gps || {};
    const risk = state.risk || {};
    const alert = state.alert || {};
    const spike = state.spike || {};

    if (this.seqTag) {
      this.seqTag.textContent = `#${state.sequence_id || this.lastSequenceId || '—'}`;
    }

    const hr = vitals.heart_rate != null ? Math.round(vitals.heart_rate) : null;
    if (this.valHR) this.valHR.textContent = hr != null ? hr : '—';
    if (this.subHR) {
      if (hr == null) this.subHR.textContent = '—';
      else if (hr > 140) this.subHR.textContent = 'High';
      else if (hr > 100) this.subHR.textContent = 'Elevated';
      else this.subHR.textContent = 'Resting';
    }

    const spo2 = vitals.spo2 != null ? Math.round(vitals.spo2) : null;
    if (this.valSpO2) this.valSpO2.textContent = spo2 != null ? spo2 : '—';
    if (this.subSpO2) {
      if (spo2 == null) this.subSpO2.textContent = '—';
      else if (spo2 < 92) this.subSpO2.textContent = 'Low';
      else this.subSpO2.textContent = 'Optimal';
    }

    const temp = vitals.temperature != null ? vitals.temperature.toFixed(1) : null;
    if (this.valTemp) this.valTemp.textContent = temp != null ? temp : '—';
    if (this.subTemp) {
      if (temp == null) this.subTemp.textContent = '—';
      else if (vitals.temperature >= 38.0) this.subTemp.textContent = 'Elevated';
      else this.subTemp.textContent = 'Normal';
    }

    if (this.valActivity) {
      this.valActivity.textContent = (activity.state || 'Rest').toLowerCase();
    }

    const riskLvl = risk.overall_level || "LOW";
    if (this.riskBadge) {
      this.riskBadge.textContent = riskLvl === 'LOW' ? 'NORMAL' : riskLvl;
      this.riskBadge.className = 'badge-risk font-mono ' + this.getRiskClass(riskLvl);
    }
    if (this.riskSummary) {
      const summary = state.escalation?.reasons?.[0];
      if (summary) {
        this.riskSummary.textContent = summary;
      } else if (riskLvl === 'LOW' || riskLvl === 'NORMAL') {
        this.riskSummary.textContent = 'Everything looks normal';
      } else {
        this.riskSummary.textContent = 'Vital signs deviating from baseline';
      }
    }
    if (this.rdsList) {
      const sources = state.decision_sources || ['Baseline', 'Clinical reference'];
      this.rdsList.textContent = sources.map(s => s.replace(/_/g, ' ').toLowerCase()).join(' · ');
    }
    if (this.riskProfileNotice) {
      const notices = state.special_notices || [];
      if (notices.length > 0) {
        this.riskProfileNotice.textContent = notices[0];
        this.riskProfileNotice.classList.remove('hidden');
      } else {
        this.riskProfileNotice.classList.add('hidden');
      }
    }

    this.renderProfileBar(state);

    const amb = vitals.ambient_temperature != null ? `${Math.round(vitals.ambient_temperature)}°C` : '—°C';
    const mq = env.raw_mq45 != null ? Math.round(env.raw_mq45) : null;
    if (this.envAmbient) this.envAmbient.textContent = amb;
    if (this.envAir) this.envAir.textContent = mq != null ? (mq > 500 ? 'Air alert' : 'Air safe') : 'Air safe';
    if (this.envGPS) this.envGPS.textContent = gps.valid ? 'GPS ok' : 'GPS searching';

    this.handleAlertModals(spike, alert, riskLvl, hr, temp);
  }

  renderProfileBar(state) {
    const prof = state.patient_profile || {};
    const bState = prof.baseline_status || "LEARNING";
    const bSummary = state.features?.baseline_summary || {};
    const contexts = state.active_condition_contexts || [];

    if (this.psbVersion) {
      this.psbVersion.textContent = `v${prof.profile_version || '1.0'}`;
    }

    if (bState === "LEARNING") {
      if (this.psbDot) this.psbDot.className = "dot dot-warning";
      if (this.psbTitle) this.psbTitle.textContent = "Calibrating baseline";
      if (this.psbHR) this.psbHR.textContent = bSummary.hr?.mean ? `~${Math.round(bSummary.hr.mean)}` : "—";
      if (this.psbSpO2) this.psbSpO2.textContent = bSummary.spo2?.mean ? `${Math.round(bSummary.spo2.mean)}%` : "—";
      if (this.psbTemp) this.psbTemp.textContent = bSummary.temp?.mean ? `${bSummary.temp.mean.toFixed(1)}°` : "—";
      if (this.psbAct) this.psbAct.textContent = "Calib";
    } else {
      if (this.psbDot) this.psbDot.className = "dot dot-success";
      if (this.psbTitle) this.psbTitle.textContent = "Personalized baseline active";
      if (this.psbHR) this.psbHR.textContent = `${Math.round(bSummary.hr?.mean || 72)}`;
      if (this.psbSpO2) this.psbSpO2.textContent = `${Math.round(bSummary.spo2?.mean || 98)}%`;
      if (this.psbTemp) this.psbTemp.textContent = `${(bSummary.temp?.mean || 36.7).toFixed(1)}°`;
      if (this.psbAct) this.psbAct.textContent = "Normal";
    }

    if (this.psbContextTags) {
      if (contexts.length > 0) {
        this.psbContextTags.classList.remove('hidden');
        this.psbContextTags.innerHTML = contexts
          .map((ctx) => `<span class="psb-ctx-chip">${ctx.replace(/_monitoring|_/g, ' ')}</span>`)
          .join('');
      } else {
        this.psbContextTags.classList.add('hidden');
      }
    }
  }

  handleAlertModals(spike, alert, riskLvl, hr, temp) {
    const latestSpike = spike.latest_spike;
    const hasActiveSpike = spike.has_active_spike;

    if (hasActiveSpike && latestSpike && !this.activeSpikeDismissed) {
      const domainName = (latestSpike.domain || "Heart rate").replace(/_/g, ' ');
      const valStr = latestSpike.domain === "TEMPERATURE" ? `${temp} °C` : `${hr} BPM`;
      
      if (this.spikeVitalName) this.spikeVitalName.textContent = domainName;
      if (this.spikeVal) this.spikeVal.textContent = valStr;
      if (this.spikeHeadline) this.spikeHeadline.textContent = latestSpike.status === "RECOVERING" ? "Monitoring recovery" : "Spike detected";
      if (this.spikeSubline) this.spikeSubline.textContent = latestSpike.message || "Sudden vital sign change.";
      
      this.spikeModal?.classList.remove('hidden');
      this.recoveredModal?.classList.add('hidden');
      this.criticalModal?.classList.add('hidden');
      return;
    } else if (!hasActiveSpike && this.spikeModal && !this.spikeModal.classList.contains('hidden')) {
      this.spikeModal.classList.add('hidden');
      this.activeSpikeDismissed = false;
    }

    if (latestSpike && latestSpike.status === "RECOVERED") {
      const valStr = latestSpike.domain === "TEMPERATURE" ? `${temp} °C` : `${hr} BPM`;
      if (this.recoveredVal) this.recoveredVal.textContent = valStr;
      this.recoveredModal?.classList.remove('hidden');
      this.spikeModal?.classList.add('hidden');
      setTimeout(() => this.recoveredModal?.classList.add('hidden'), 5000);
      return;
    }

    if (riskLvl === 'CRITICAL' && !this.activeCriticalDismissed) {
      if (this.criticalHeadline) this.criticalHeadline.textContent = "Persistent vital deviation";
      if (this.criticalReason) this.criticalReason.textContent = alert.reason || "Multiple signals deviating at rest.";
      this.criticalModal?.classList.remove('hidden');
      this.spikeModal?.classList.add('hidden');
      this.recoveredModal?.classList.add('hidden');
    } else if (riskLvl !== 'CRITICAL') {
      this.criticalModal?.classList.add('hidden');
      this.activeCriticalDismissed = false;
    }
  }

  getRiskClass(level) {
    switch (level) {
      case 'CRITICAL': return 'risk-critical';
      case 'ELEVATED': return 'risk-elevated';
      case 'EARLY_WARNING':
      case 'OBSERVATION': return 'risk-obs';
      default: return 'risk-low';
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.aarogyaWatch = new AarogyaCompanion();
});
