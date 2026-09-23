/**
 * AAROGYA-SHIELD: Smartwatch Wearable Controller
 * Renders realistic wearable UI with 7 distinct screens,
 * supports touch swipe, keyboard navigation, and crown clicks.
 */

export class SmartwatchController {
  constructor() {
    this.currentPage = 0;
    this.totalPages = 7;
    this.screenInner = document.getElementById('watch-screen-inner');
    this.dots = document.querySelectorAll('.screen-dots .dot');
    this.crownBtn = document.getElementById('watch-crown');
    this.watchScreen = document.getElementById('watch-screen');

    // Rolling buffers for mini sparklines inside watch
    this.hrHistory = [72, 73, 74, 73, 74, 75, 74];
    this.spo2History = [98, 98, 98, 97, 98, 98, 98];

    this._initNavigation();
    this._startClock();
  }

  _initNavigation() {
    // Crown Click -> Next Page
    this.crownBtn?.addEventListener('click', () => {
      this.goToPage((this.currentPage + 1) % this.totalPages);
    });

    // Dot indicators
    this.dots.forEach((dot) => {
      dot.addEventListener('click', (e) => {
        const target = parseInt(e.currentTarget.getAttribute('data-target'), 10);
        if (!isNaN(target)) this.goToPage(target);
      });
    });

    // Keyboard Arrow Keys
    window.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.key === 'ArrowRight') {
        this.goToPage((this.currentPage + 1) % this.totalPages);
      } else if (e.key === 'ArrowLeft') {
        this.goToPage((this.currentPage - 1 + this.totalPages) % this.totalPages);
      }
    });

    // Touch and Mouse Swipe on Watch Screen
    let startX = 0;
    let isDown = false;

    this.watchScreen?.addEventListener('mousedown', (e) => {
      startX = e.clientX;
      isDown = true;
    });

    window.addEventListener('mouseup', (e) => {
      if (!isDown) return;
      isDown = false;
      const diffX = e.clientX - startX;
      if (diffX < -40) {
        this.goToPage((this.currentPage + 1) % this.totalPages);
      } else if (diffX > 40) {
        this.goToPage((this.currentPage - 1 + this.totalPages) % this.totalPages);
      }
    });

    // Touch Events
    this.watchScreen?.addEventListener('touchstart', (e) => {
      startX = e.touches[0].clientX;
    }, { passive: true });

    this.watchScreen?.addEventListener('touchend', (e) => {
      const diffX = e.changedTouches[0].clientX - startX;
      if (diffX < -40) {
        this.goToPage((this.currentPage + 1) % this.totalPages);
      } else if (diffX > 40) {
        this.goToPage((this.currentPage - 1 + this.totalPages) % this.totalPages);
      }
    }, { passive: true });
  }

  goToPage(index) {
    if (index < 0 || index >= this.totalPages) return;
    this.currentPage = index;
    const offset = -(index * (100 / this.totalPages));
    if (this.screenInner) {
      this.screenInner.style.transform = `translateX(${offset}%)`;
    }
    this.dots.forEach((dot, idx) => {
      dot.classList.toggle('active', idx === index);
    });
  }

  _startClock() {
    const clockEl = document.getElementById('w-clock');
    const updateTime = () => {
      const now = new Date();
      const hrs = String(now.getHours()).padStart(2, '0');
      const mins = String(now.getMinutes()).padStart(2, '0');
      if (clockEl) clockEl.textContent = `${hrs}:${mins}`;
    };
    updateTime();
    setInterval(updateTime, 1000);
  }

  updateDisplay(payload, latencyMs = 0) {
    if (!payload) return;

    const raw = payload.raw_sensors || payload.sensor_data || {};
    const features = payload.features || {};
    const preds = payload.ml_predictions || payload.predictions || {};
    const escalation = payload.escalation || {};
    const baseline = payload.baseline_summary || {};
    const alert = payload.active_alert || payload.alert || null;

    const overall = preds.overall_health_risk || preds.overall || {};
    const overallScore = overall.score !== undefined ? overall.score : 0.08;
    const overallLevel = escalation.escalated_level || overall.risk_level || 'LOW';

    // 1. SCREEN 1: HOME
    const homeBadge = document.getElementById('w-home-status-badge');
    const homeDot = document.getElementById('w-home-status-dot');
    const homeText = document.getElementById('w-home-status-text');
    if (homeText) homeText.textContent = overallLevel.replace('_', ' ');

    if (homeBadge && homeDot) {
      homeBadge.className = 'status-badge-lg ' + this._getLevelClass(overallLevel);
      homeDot.className = 'pulse-dot ' + this._getLevelDotClass(overallLevel);
    }

    const hr = Math.round(raw.heart_rate || features.heart_rate || 74);
    const spo2 = Math.round(raw.spo2 || features.spo2 || 98);
    const temp = (raw.body_temperature || features.body_temperature || 36.7).toFixed(1);

    this._setText('w-home-hr', hr);
    this._setText('w-home-spo2', spo2);
    this._setText('w-home-temp', temp);
    this._setText('w-home-risk-score', overallScore.toFixed(2));
    this._setText('w-home-activity', features.activity_level || 'REST');

    // 2. SCREEN 2: VITALS
    this._setText('w-vitals-hr', hr);
    this._setText('w-vitals-spo2', spo2);
    this._setText('w-vitals-temp', `${temp}°C`);
    const ppg = Math.round((raw.ppg_quality || features.ppg_quality || 0.96) * 100);
    this._setText('w-vitals-ppg', `${ppg}%`);

    // Baseline deviations
    const hrDev = baseline.heart_rate?.difference !== undefined ? baseline.heart_rate.difference : (features.hr_deviation ? features.hr_deviation * 72 : 0);
    const hrDevSign = hrDev >= 0 ? `+${Math.round(hrDev)}` : `${Math.round(hrDev)}`;
    this._setText('w-vitals-hr-dev', `${hrDevSign} from base`);

    const spo2Dev = baseline.spo2?.difference !== undefined ? baseline.spo2.difference : 0;
    const spo2Text = Math.abs(spo2Dev) < 0.5 ? 'stable' : `${spo2Dev > 0 ? '+' : ''}${spo2Dev.toFixed(1)}% base`;
    this._setText('w-vitals-spo2-dev', spo2Text);

    // Update Sparklines
    this.hrHistory.push(hr);
    if (this.hrHistory.length > 20) this.hrHistory.shift();
    this.spo2History.push(spo2);
    if (this.spo2History.length > 20) this.spo2History.shift();
    this._renderSparkline('svg-hr-spark', this.hrHistory, 40, 180);
    this._renderSparkline('svg-spo2-spark', this.spo2History, 80, 100);

    // 3. SCREEN 3: RISK
    this._setText('w-risk-score', overallScore.toFixed(2));
    const riskLvlEl = document.getElementById('w-risk-level');
    if (riskLvlEl) {
      riskLvlEl.textContent = overallLevel.replace('_', ' ');
      riskLvlEl.className = 'w-score-lvl font-mono ' + this._getLevelTextClass(overallLevel);
    }
    const trendText = features.hr_trend > 0.3 ? '↑ INCREASING' : features.hr_trend < -0.3 ? '↓ DECREASING' : '→ STABLE';
    this._setText('w-risk-trend', trendText);

    // Sub risks
    this._setSubRisk('w-sub-resp', preds.respiratory_risk?.risk_level);
    this._setSubRisk('w-sub-oxy', preds.oxygenation_anomaly?.risk_level);
    this._setSubRisk('w-sub-heat', preds.heat_stress_risk?.risk_level);
    this._setSubRisk('w-sub-fatigue', preds.fatigue_strain_risk?.risk_level);
    this._setSubRisk('w-sub-env', preds.environmental_exposure_risk?.risk_level);
    this._setSubRisk('w-sub-gen', preds.general_health_anomaly?.risk_level);

    // 4. SCREEN 4: ENVIRONMENT
    const ambTemp = (raw.ambient_temperature || features.ambient_temperature || 28.0).toFixed(1);
    const hum = Math.round(raw.humidity || features.humidity || 60);
    const mq45 = Math.round(raw.mq45 || features.mq45 || 180);

    this._setText('w-env-amb', `${ambTemp}°C`);
    this._setText('w-env-hum', `${hum}%`);
    this._setText('w-env-mq', mq45);

    const envLevel = preds.environmental_exposure_risk?.risk_level || 'LOW';
    const envStatusEl = document.getElementById('w-env-status');
    if (envStatusEl) {
      envStatusEl.textContent = envLevel.replace('_', ' ');
      envStatusEl.className = 'w-env-mq-val font-mono ' + this._getLevelTextClass(envLevel);
    }

    // 5. SCREEN 5: ACTIVITY
    const actState = features.activity_level || 'REST';
    this._setText('w-act-state', actState);
    const isFall = features.is_fall_candidate || features.activity_state === 4;
    const fallBanner = document.getElementById('w-fall-banner');
    if (fallBanner) {
      fallBanner.classList.toggle('hidden', !isFall);
    }

    const mag = features.acceleration_magnitude || 0.98;
    this._setText('w-act-mag', `${mag.toFixed(2)} g`);
    this._setText('w-act-x', (raw.accel_x !== undefined ? raw.accel_x : 0.02).toFixed(2));
    this._setText('w-act-y', (raw.accel_y !== undefined ? raw.accel_y : 0.01).toFixed(2));
    this._setText('w-act-z', (raw.accel_z !== undefined ? raw.accel_z : 0.98).toFixed(2));

    // 6. SCREEN 6: ALERT
    const alertNone = document.getElementById('w-alert-none');
    const alertActive = document.getElementById('w-alert-active');

    if (!alert || alert.acknowledged) {
      alertNone?.classList.remove('hidden');
      alertActive?.classList.add('hidden');
    } else {
      alertNone?.classList.add('hidden');
      alertActive?.classList.remove('hidden');

      const isCritical = alert.risk_level === 'CRITICAL';
      alertActive.className = 'w-alert-box ' + (isCritical ? 'critical' : '');
      this._setText('w-alert-sym', isCritical ? '!!' : '⚠');
      this._setText('w-alert-lvl', alert.risk_level?.replace('_', ' ') || 'ALERT');
      this._setText('w-alert-msg', alert.message || 'Physiological threshold deviation.');

      const details = Array.isArray(alert.contributing_parameters) ? alert.contributing_parameters.join(', ') : '';
      this._setText('w-alert-details', details || 'Multiple deviations detected.');
      const lat = alert.latitude !== undefined ? alert.latitude.toFixed(3) : '10.662';
      const lon = alert.longitude !== undefined ? alert.longitude.toFixed(3) : '76.891';
      this._setText('w-alert-loc', `${lat}, ${lon}`);
    }

    // 7. SCREEN 7: SYSTEM
    const packetTime = raw.timestamp ? new Date(raw.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
    this._setText('w-sys-packet', packetTime);
    if (latencyMs > 0) {
      this._setText('w-sys-latency', `${latencyMs} ms`);
    }

    const modelName = preds.model_version ? `XGBoost v1 (${preds.model_version})` : 'XGBoost v1 (1.0.0-edge)';
    this._setText('w-sys-model-name', `MODEL: ${modelName}`);
  }

  _setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  _setSubRisk(id, level = 'LOW') {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = level.replace('_', ' ');
    el.className = this._getLevelTextClass(level);
  }

  _getLevelClass(lvl) {
    switch (lvl) {
      case 'CRITICAL': return 'lvl-critical';
      case 'ELEVATED': return 'lvl-elevated';
      case 'EARLY_WARNING': return 'lvl-early';
      default: return 'lvl-low';
    }
  }

  _getLevelDotClass(lvl) {
    switch (lvl) {
      case 'CRITICAL': return 'red';
      case 'ELEVATED': return 'orange';
      case 'EARLY_WARNING': return 'amber';
      default: return 'green';
    }
  }

  _getLevelTextClass(lvl) {
    switch (lvl) {
      case 'CRITICAL': return 'text-red font-bold';
      case 'ELEVATED': return 'text-orange font-bold';
      case 'EARLY_WARNING': return 'text-amber font-bold';
      default: return 'text-green';
    }
  }

  _renderSparkline(svgId, data, minVal, maxVal) {
    const svg = document.getElementById(svgId);
    if (!svg || data.length < 2) return;

    const width = 100;
    const height = 24;
    const range = maxVal - minVal || 1;

    const points = data.map((val, idx) => {
      const x = (idx / (data.length - 1)) * width;
      const normY = Math.max(0, Math.min(1, (val - minVal) / range));
      const y = height - normY * (height - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    svg.innerHTML = `<polyline points="${points}" fill="none" stroke="#38bdf8" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />`;
  }
}
