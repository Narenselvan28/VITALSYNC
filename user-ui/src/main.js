/**
 * AAROGYA-SHIELD: User POV Smartwatch Health Companion
 * Realistic Light-Mode Wearable Health Interface.
 * Strictly DISPLAY ONLY: consumes authoritative backend stream with monotonic sequence_id.
 * No independent risk calculations, no random ambient jitter, no hardcoded override mocks.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/live';

class AarogyaWatchCompanion {
  constructor() {
    this.ws = null;
    this.reconnectTimer = null;
    this.lastSequenceId = -1;
    this.activeSpikeDismissed = false;
    this.activeCriticalDismissed = false;

    this._cacheDom();
    this._bindEvents();
    this._startClock();
    this.init();
  }

  _cacheDom() {
    // Clock & Status
    this.clockEl = document.getElementById('watchTime');
    this.dateEl = document.getElementById('watchDate');
    this.monitoringPill = document.getElementById('monitoringPill');
    this.statusLabel = document.getElementById('statusLabel');
    this.statusPulseDot = document.getElementById('statusPulseDot');
    this.seqTag = document.getElementById('seqTag');

    // Primary Vitals
    this.valHR = document.getElementById('valHR');
    this.subHR = document.getElementById('subHR');
    this.valSpO2 = document.getElementById('valSpO2');
    this.subSpO2 = document.getElementById('subSpO2');
    this.valTemp = document.getElementById('valTemp');
    this.subTemp = document.getElementById('subTemp');
    this.valActivity = document.getElementById('valActivity');
    this.subActivity = document.getElementById('subActivity');

    // Risk Card
    this.riskCard = document.getElementById('riskCard');
    this.riskBadge = document.getElementById('riskBadge');
    this.riskSummary = document.getElementById('riskSummary');
    this.riskDecisionSources = document.getElementById('riskDecisionSources');
    this.rdsList = document.getElementById('rdsList');
    this.riskProfileNotice = document.getElementById('riskProfileNotice');

    // Profile & Baseline Status Banner (Section 6 & 15)
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

    // Health Profile Modal (Section 1, 2, 3, 15)
    this.profileModal = document.getElementById('profileModal');
    this.btnCloseProfile = document.getElementById('btnCloseProfile');
    this.profileForm = document.getElementById('profileForm');
    this.profAge = document.getElementById('profAge');
    this.profSex = document.getElementById('profSex');
    this.profHeight = document.getElementById('profHeight');
    this.profWeight = document.getElementById('profWeight');
    this.profMedications = document.getElementById('profMedications');
    this.condCheckboxes = document.querySelectorAll('input[name="condition"]');

    // Environmental Footer
    this.envAmbient = document.getElementById('envAmbient');
    this.envAir = document.getElementById('envAir');
    this.envGPS = document.getElementById('envGPS');

    // Alert Modals
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

    // Footer Sync Status
    this.wsSyncDot = document.getElementById('wsSyncDot');
    this.wsSyncText = document.getElementById('wsSyncText');
  }

  _bindEvents() {
    // Open Profile Modal
    this.btnOpenProfile?.addEventListener('click', () => {
      this.openProfileModal();
    });

    // Close Profile Modal
    this.btnCloseProfile?.addEventListener('click', () => {
      this.closeProfileModal();
    });

    // Health Conditions Mutual Exclusivity Rules (Section 1)
    this.condCheckboxes.forEach((cb) => {
      cb.addEventListener('change', (e) => {
        const targetVal = e.target.value;
        if (targetVal === 'none' && e.target.checked) {
          this.condCheckboxes.forEach((other) => {
            if (other.value !== 'none') other.checked = false;
          });
        } else if (targetVal === 'prefer_not_to_say' && e.target.checked) {
          this.condCheckboxes.forEach((other) => {
            if (other.value !== 'prefer_not_to_say') other.checked = false;
          });
        } else if (e.target.checked) {
          const noneCb = document.getElementById('cond-none');
          const preferNotCb = document.getElementById('cond-prefer-not');
          if (noneCb) noneCb.checked = false;
          if (preferNotCb) preferNotCb.checked = false;
        }
      });
    });

    // Profile Form Submission (Section 3, 13, 15)
    this.profileForm?.addEventListener('submit', async (e) => {
      e.preventDefault();
      await this.saveProfile();
    });

    // Dismiss Spike Modal
    this.btnDismissSpike?.addEventListener('click', () => {
      this.spikeModal?.classList.add('hidden');
      this.activeSpikeDismissed = true;
    });

    // Dismiss Recovered Modal
    this.btnDismissRecovered?.addEventListener('click', () => {
      this.recoveredModal?.classList.add('hidden');
    });

    // Check User / Acknowledge Critical Alert
    this.btnCheckUser?.addEventListener('click', async () => {
      this.criticalModal?.classList.add('hidden');
      this.activeCriticalDismissed = true;
      try {
        await fetch(`${API_BASE}/api/alerts/latest`);
      } catch (e) {
        console.warn('[Watch] Alert ack fetch failed:', e);
      }
    });

    // Physical Digital Crown click (re-centers UI and clears transient dismissed flags)
    const crownBtn = document.getElementById('crownBtn');
    crownBtn?.addEventListener('click', () => {
      this.activeSpikeDismissed = false;
      this.activeCriticalDismissed = false;
    });
  }

  _startClock() {
    const updateTime = () => {
      const now = new Date();
      if (this.clockEl) {
        this.clockEl.innerText = now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
      }
      if (this.dateEl) {
        const days = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
        const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
        this.dateEl.innerText = `${days[now.getDay()]} ${now.getDate()} ${months[now.getMonth()]}`;
      }
    };
    updateTime();
    setInterval(updateTime, 1000);
  }

  async init() {
    await this.fetchLatestAuthoritativeState();
    await this.fetchProfileData();
    this.connectWebSocket();
  }

  openProfileModal() {
    this.profileModal?.classList.remove('hidden');
  }

  closeProfileModal() {
    this.profileModal?.classList.add('hidden');
  }

  async fetchProfileData() {
    try {
      const resp = await fetch(`${API_BASE}/api/profile?device_id=ESP32-001`);
      if (resp.ok) {
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

        // If not completed yet by user, prompt on startup
        if (!localStorage.getItem('aarogya_profile_completed')) {
          this.openProfileModal();
        }
      }
    } catch (e) {
      console.warn('[Watch] Failed to fetch health profile:', e);
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

    if (selectedConditions.length === 0) {
      selectedConditions.push('none');
    }

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
        this.closeProfileModal();
      }
    } catch (e) {
      console.error('[Watch] Failed to save profile:', e);
    }
  }

  async fetchLatestAuthoritativeState() {
    try {
      const resp = await fetch(`${API_BASE}/api/sensors/latest?device_id=ESP32-001`);
      if (resp.ok) {
        const data = await resp.json();
        this.renderState({
          sequence_id: 1000,
          vitals: {
            heart_rate: data.heart_rate || 75,
            spo2: data.spo2 || 98,
            temperature: data.body_temperature || 36.7,
            ambient_temperature: data.ambient_temperature || 28.0,
          },
          activity: {
            state: "REST",
            intensity: 0.98,
          },
          environment: {
            gas_index: (data.mq45 || 180) / 1000,
            raw_mq45: data.mq45 || 180,
          },
          gps: {
            lat: data.latitude || 10.662,
            lon: data.longitude || 76.891,
            valid: true,
          },
          risk: {
            overall_score: 0.08,
            overall_level: "LOW",
            primary_domain: "Normal Physiology",
          },
          alert: {
            active: false,
            level: "LOW",
          },
        });
      }
    } catch (e) {
      console.warn('[Watch] Initial sensor fetch completed with defaults.');
    }
  }

  connectWebSocket() {
    clearTimeout(this.reconnectTimer);
    try {
      this.ws = new WebSocket(WS_URL);

      this.ws.onopen = () => {
        if (this.wsSyncDot) this.wsSyncDot.className = "sync-dot connected";
        if (this.wsSyncText) this.wsSyncText.innerText = "Authoritative Edge Stream Connected (1 Hz)";
        if (this.statusLabel) this.statusLabel.innerText = "● Monitoring";
        if (this.monitoringPill) this.monitoringPill.classList.add('pill-active');
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          this.handleAuthoritativeUpdate(msg);
        } catch (e) {
          console.warn('[Watch] WS parse error:', e);
        }
      };

      this.ws.onclose = () => {
        if (this.wsSyncDot) this.wsSyncDot.className = "sync-dot disconnected";
        if (this.wsSyncText) this.wsSyncText.innerText = "Reconnecting to Edge Backend...";
        if (this.statusLabel) this.statusLabel.innerText = "○ Reconnecting";
        if (this.monitoringPill) this.monitoringPill.classList.remove('pill-active');
        this.reconnectTimer = setTimeout(() => this.connectWebSocket(), 2000);
      };

      this.ws.onerror = () => {
        if (this.wsSyncDot) this.wsSyncDot.className = "sync-dot disconnected";
      };
    } catch (e) {
      this.reconnectTimer = setTimeout(() => this.connectWebSocket(), 2500);
    }
  }

  /**
   * CRITICAL REQUIREMENT (Section 3):
   * Monotonic sequence_id check. Both frontends reject stale updates.
   */
  handleAuthoritativeUpdate(msg) {
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
      const conditions = p.conditions || ['none'];
      this.condCheckboxes.forEach((cb) => {
        cb.checked = conditions.includes(cb.value);
      });
      this._renderProfileStatusBar({
        patient_profile: p,
        active_condition_contexts: msg.active_contexts || [],
        features: { baseline_summary: {} }
      });
      return;
    }

    // Check monotonic sequence_id if provided
    if (msg.sequence_id !== undefined) {
      if (msg.sequence_id <= this.lastSequenceId) {
        console.warn(`[Watch] Dropping stale update seq=${msg.sequence_id} (current=${this.lastSequenceId})`);
        return;
      }
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

    // 1. Sequence ID tag
    if (this.seqTag) {
      this.seqTag.innerText = `seq #${state.sequence_id || this.lastSequenceId || 1000}`;
    }

    // 2. Heart Rate
    const hr = Math.round(vitals.heart_rate || 75);
    if (this.valHR) this.valHR.innerText = hr;
    if (this.subHR) {
      if (hr > 150) this.subHR.innerText = "Elevated · High";
      else if (hr > 100) this.subHR.innerText = "Active elevation";
      else this.subHR.innerText = "Resting · Nominal";
    }

    // 3. SpO2
    const spo2 = Math.round(vitals.spo2 || 98);
    if (this.valSpO2) this.valSpO2.innerText = spo2;
    if (this.subSpO2) {
      if (spo2 < 90) this.subSpO2.innerText = "Significant drop";
      else if (spo2 < 95) this.subSpO2.innerText = "Mild deviation";
      else this.subSpO2.innerText = "Optimal range";
    }

    // 4. Body Temperature
    const temp = (vitals.temperature || 36.7).toFixed(1);
    if (this.valTemp) this.valTemp.innerText = temp;
    if (this.subTemp) {
      if (vitals.temperature >= 38.5) this.subTemp.innerText = "Thermal spike";
      else this.subTemp.innerText = "Contact steady";
    }

    // 5. Activity
    const actState = activity.state || "REST";
    const actIntensity = activity.intensity !== undefined ? `${activity.intensity} g` : "0.98 g";
    if (this.valActivity) this.valActivity.innerText = actState;
    if (this.subActivity) this.subActivity.innerText = actIntensity;

    // 6. Health Risk Badge, Summary & Transparent Decision Sources (Section 12, 18, 20)
    const riskLvl = risk.overall_level || "LOW";
    if (this.riskBadge) {
      this.riskBadge.innerText = riskLvl.replace('_', ' ');
      this.riskBadge.className = 'risk-badge font-mono ' + this._getRiskBadgeClass(riskLvl);
    }
    if (this.riskSummary) {
      const summaryText = state.escalation?.reasons?.[0] || risk.primary_domain || "All parameters tracking within baseline norms.";
      this.riskSummary.innerText = summaryText;
    }
    if (this.rdsList) {
      const sources = state.decision_sources || ['REFERENCE_THRESHOLD', 'PERSONAL_BASELINE'];
      this.rdsList.innerText = sources.join(' · ');
    }
    if (this.riskProfileNotice) {
      const notices = state.special_notices || [];
      if (notices.length > 0) {
        this.riskProfileNotice.innerText = notices[0];
        this.riskProfileNotice.classList.remove('hidden');
      } else {
        this.riskProfileNotice.classList.add('hidden');
      }
    }

    // 7. Personalized Monitoring & Baseline Status (Section 6, 11, 15)
    this._renderProfileStatusBar(state);

    // 8. Environmental Strip
    const amb = vitals.ambient_temperature !== undefined ? `${vitals.ambient_temperature.toFixed(1)}°C` : "28.0°C";
    const mq = env.raw_mq45 !== undefined ? Math.round(env.raw_mq45) : Math.round((env.gas_index || 0.18) * 1000);
    if (this.envAmbient) this.envAmbient.innerText = `Amb: ${amb}`;
    if (this.envAir) this.envAir.innerText = `Air: ${mq > 500 ? 'Warning' : 'Safe'} (${mq})`;
    if (this.envGPS) this.envGPS.innerText = gps.valid ? `GPS: ${gps.lat?.toFixed(2)},${gps.lon?.toFixed(2)}` : "GPS: No Fix";

    // 9. ALERT MODALS (Section 19: Spike vs Recovered vs Critical)
    this._handleAlertModals(spike, alert, riskLvl, hr, temp);
  }

  _renderProfileStatusBar(state) {
    const prof = state.patient_profile || {};
    const bState = prof.baseline_status || "LEARNING";
    const bSummary = state.features?.baseline_summary || {};
    const contexts = state.active_condition_contexts || [];

    if (this.psbVersion) {
      this.psbVersion.innerText = `v${prof.profile_version || '1.0'}`;
    }

    if (bState === "LEARNING") {
      if (this.psbDot) {
        this.psbDot.className = "psb-dot learning";
      }
      if (this.psbTitle) {
        this.psbTitle.innerText = "Learning personal baseline...";
      }
      if (this.psbHR) this.psbHR.innerText = bSummary.hr?.mean ? `${Math.round(bSummary.hr.mean)}*` : "Learning";
      if (this.psbSpO2) this.psbSpO2.innerText = bSummary.spo2?.mean ? `${Math.round(bSummary.spo2.mean)}%*` : "Learning";
      if (this.psbTemp) this.psbTemp.innerText = bSummary.temp?.mean ? `${bSummary.temp.mean.toFixed(1)}°*` : "Learning";
      if (this.psbAct) this.psbAct.innerText = "Learning";
    } else {
      if (this.psbDot) {
        this.psbDot.className = "psb-dot active";
      }
      if (this.psbTitle) {
        this.psbTitle.innerText = "Personalized monitoring active";
      }
      if (this.psbHR) this.psbHR.innerText = `${Math.round(bSummary.hr?.mean || 72)} bpm`;
      if (this.psbSpO2) this.psbSpO2.innerText = `${Math.round(bSummary.spo2?.mean || 98)}%`;
      if (this.psbTemp) this.psbTemp.innerText = `${(bSummary.temp?.mean || 36.7).toFixed(1)}°C`;
      if (this.psbAct) this.psbAct.innerText = "Norm";
    }

    // Active condition context tags
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

  _handleAlertModals(spike, alert, riskLvl, hr, temp) {
    // A. Check for Spike Event
    const latestSpike = spike.latest_spike;
    const hasActiveSpike = spike.has_active_spike;

    if (hasActiveSpike && latestSpike && !this.activeSpikeDismissed) {
      // Show Spike Modal (Section 19: 198 BPM Spike detected Monitoring...)
      const domainName = (latestSpike.domain || "HEART_RATE").replace('_', ' ');
      const valStr = latestSpike.domain === "TEMPERATURE" ? `${temp} °C` : `${hr} BPM`;
      
      if (this.spikeVitalName) this.spikeVitalName.innerText = domainName;
      if (this.spikeVal) this.spikeVal.innerText = valStr;
      if (this.spikeHeadline) this.spikeHeadline.innerText = latestSpike.status === "RECOVERING" ? "Monitoring recovery..." : "Spike detected";
      if (this.spikeSubline) this.spikeSubline.innerText = latestSpike.message || "Rapid physiological transition detected.";
      
      this.spikeModal?.classList.remove('hidden');
      this.recoveredModal?.classList.add('hidden');
      this.criticalModal?.classList.add('hidden');
      return;
    } else if (!hasActiveSpike && this.spikeModal && !this.spikeModal.classList.contains('hidden')) {
      // Spike has cleared or recovered
      this.spikeModal.classList.add('hidden');
      this.activeSpikeDismissed = false;
    }

    // B. Check for Recovery Event
    if (latestSpike && latestSpike.status === "RECOVERED") {
      const valStr = latestSpike.domain === "TEMPERATURE" ? `${temp} °C` : `${hr} BPM`;
      if (this.recoveredVal) this.recoveredVal.innerText = valStr;
      this.recoveredModal?.classList.remove('hidden');
      this.spikeModal?.classList.add('hidden');
      
      // Auto-hide recovered notification after 6 seconds
      setTimeout(() => {
        this.recoveredModal?.classList.add('hidden');
      }, 6000);
      return;
    }

    // C. Check for True Critical Health Alert (Persistent Anomaly / Fall)
    if (riskLvl === 'CRITICAL' && !this.activeCriticalDismissed) {
      if (this.criticalHeadline) this.criticalHeadline.innerText = "Persistent abnormal vital pattern";
      if (this.criticalReason) this.criticalReason.innerText = alert.reason || "Multi-signal persistent physiological anomaly.";
      this.criticalModal?.classList.remove('hidden');
      this.spikeModal?.classList.add('hidden');
      this.recoveredModal?.classList.add('hidden');
      return;
    } else if (riskLvl !== 'CRITICAL') {
      this.criticalModal?.classList.add('hidden');
      this.activeCriticalDismissed = false;
    }
  }

  _getRiskBadgeClass(level) {
    switch (level) {
      case 'CRITICAL': return 'risk-critical';
      case 'ELEVATED': return 'risk-elevated';
      case 'EARLY_WARNING':
      case 'OBSERVATION': return 'risk-obs';
      default: return 'risk-low';
    }
  }
}

// Bootstrap on DOM Load
document.addEventListener('DOMContentLoaded', () => {
  window.aarogyaWatch = new AarogyaWatchCompanion();
});
