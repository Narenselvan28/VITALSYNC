export class SmartwatchController {
  constructor() {
    this.currentPage = 0;
    this.totalPages = 7;
    this.screenInner = document.getElementById('watch-screen-inner');
    this.dots = document.querySelectorAll('.carousel-dots .dot-btn, .screen-dots .dot');
    this.crownBtn = document.getElementById('watch-crown');
    this.watchScreen = document.getElementById('watch-screen');
    this.frame = document.getElementById('smartwatch-frame');

    this.hrHistory = [72, 73, 74, 73, 74, 75, 74];
    this.spo2History = [98, 98, 98, 97, 98, 98, 98];

    this.initNavigation();
    this.startClock();
  }

  initNavigation() {
    this.crownBtn?.addEventListener('click', () => {
      this.goToPage((this.currentPage + 1) % this.totalPages);
    });

    this.dots.forEach((dot) => {
      dot.addEventListener('click', (e) => {
        const target = parseInt(e.currentTarget.getAttribute('data-target'), 10);
        if (!isNaN(target)) this.goToPage(target);
      });
    });

    window.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.key === 'ArrowRight') {
        this.goToPage((this.currentPage + 1) % this.totalPages);
      } else if (e.key === 'ArrowLeft') {
        this.goToPage((this.currentPage - 1 + this.totalPages) % this.totalPages);
      }
    });

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

  startClock() {
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

    // Page 0: Home
    const homeBadge = document.getElementById('w-home-status-badge');
    const homeDot = document.getElementById('w-home-status-dot');
    const homeText = document.getElementById('w-home-status-text');
    if (homeText) {
      homeText.textContent = overallLevel === 'LOW' ? 'Normal' : overallLevel.replace(/_/g, ' ');
    }

    if (homeBadge && homeDot) {
      homeDot.className = 'dot ' + (overallLevel === 'CRITICAL' ? 'dot-danger' : overallLevel === 'ELEVATED' || overallLevel === 'EARLY_WARNING' ? 'dot-warning' : 'dot-success');
    }

    const hr = Math.round(raw.heart_rate || features.heart_rate || 74);
    const spo2 = Math.round(raw.spo2 || features.spo2 || 98);
    const temp = (raw.body_temperature || features.body_temperature || 36.7).toFixed(1);

    this.setText('w-home-hr', hr);
    this.setText('w-home-spo2', spo2);
    this.setText('w-home-temp', temp);
    this.setText('w-home-risk-score', overallScore.toFixed(2));
    this.setText('w-home-activity', (features.activity_level || 'Rest').toLowerCase());

    // Page 1: Vitals
    this.setText('w-vitals-hr', hr);
    this.setText('w-vitals-spo2', spo2);
    this.setText('w-vitals-temp', `${temp}°C`);
    const ppg = Math.round((raw.ppg_quality || features.ppg_quality || 0.96) * 100);
    this.setText('w-vitals-ppg', `${ppg}%`);

    const hrDev = baseline.heart_rate?.difference !== undefined ? baseline.heart_rate.difference : (features.hr_deviation ? features.hr_deviation * 72 : 0);
    const hrDevSign = hrDev >= 0 ? `+${Math.round(hrDev)}` : `${Math.round(hrDev)}`;
    this.setText('w-vitals-hr-dev', `${hrDevSign} baseline`);

    const spo2Dev = baseline.spo2?.difference !== undefined ? baseline.spo2.difference : 0;
    const spo2Text = Math.abs(spo2Dev) < 0.5 ? 'stable' : `${spo2Dev > 0 ? '+' : ''}${spo2Dev.toFixed(1)}% base`;
    this.setText('w-vitals-spo2-dev', spo2Text);

    this.hrHistory.push(hr);
    if (this.hrHistory.length > 20) this.hrHistory.shift();
    this.spo2History.push(spo2);
    if (this.spo2History.length > 20) this.spo2History.shift();
    this.renderSparkline('svg-hr-spark', this.hrHistory, 40, 180);
    this.renderSparkline('svg-spo2-spark', this.spo2History, 80, 100);

    // Page 2: Risk
    this.setText('w-risk-score', overallScore.toFixed(2));
    const riskLvlEl = document.getElementById('w-risk-level');
    if (riskLvlEl) {
      riskLvlEl.textContent = overallLevel === 'LOW' ? 'Low' : overallLevel.replace(/_/g, ' ');
    }
    const trendText = features.hr_trend > 0.3 ? 'Rising' : features.hr_trend < -0.3 ? 'Falling' : 'Stable';
    this.setText('w-risk-trend', trendText);

    this.setSubRisk('w-sub-resp', preds.respiratory_risk?.risk_level);
    this.setSubRisk('w-sub-oxy', preds.oxygenation_anomaly?.risk_level);
    this.setSubRisk('w-sub-heat', preds.heat_stress_risk?.risk_level);
    this.setSubRisk('w-sub-fatigue', preds.fatigue_strain_risk?.risk_level);
    this.setSubRisk('w-sub-env', preds.environmental_exposure_risk?.risk_level);
    this.setSubRisk('w-sub-gen', preds.general_health_anomaly?.risk_level);

    // Page 3: Environment
    const ambTemp = (raw.ambient_temperature || features.ambient_temperature || 28.0).toFixed(1);
    const hum = Math.round(raw.humidity || features.humidity || 60);
    const mq45 = Math.round(raw.mq45 || features.mq45 || 180);

    this.setText('w-env-amb', `${ambTemp}°C`);
    this.setText('w-env-hum', `${hum}%`);
    this.setText('w-env-mq', mq45);

    const envLevel = preds.environmental_exposure_risk?.risk_level || 'LOW';
    const envStatusEl = document.getElementById('w-env-status');
    if (envStatusEl) {
      envStatusEl.textContent = envLevel === 'LOW' ? 'Safe' : envLevel.replace(/_/g, ' ');
    }

    // Page 4: Activity
    const actState = features.activity_level || 'Rest';
    this.setText('w-act-state', actState);
    const isFall = features.is_fall_candidate || features.activity_state === 4;
    const fallBanner = document.getElementById('w-fall-banner');
    if (fallBanner) fallBanner.classList.toggle('hidden', !isFall);

    const mag = features.acceleration_magnitude || 0.98;
    this.setText('w-act-mag', `${mag.toFixed(2)} g`);
    this.setText('w-act-x', (raw.accel_x !== undefined ? raw.accel_x : 0.02).toFixed(2));
    this.setText('w-act-y', (raw.accel_y !== undefined ? raw.accel_y : 0.01).toFixed(2));
    this.setText('w-act-z', (raw.accel_z !== undefined ? raw.accel_z : 0.98).toFixed(2));

    // Page 5: Alert
    const hasAlert = alert && (alert.active || alert.level === 'CRITICAL' || overallLevel === 'CRITICAL');
    const alertNone = document.getElementById('w-alert-none');
    const alertActive = document.getElementById('w-alert-active');

    if (alertNone && alertActive) {
      alertNone.classList.toggle('hidden', hasAlert);
      alertActive.classList.toggle('hidden', !hasAlert);
      if (hasAlert) {
        this.setText('w-alert-lvl', alert.level || overallLevel);
        this.setText('w-alert-msg', alert.message || 'Persistent physiological deviation.');
        this.setText('w-alert-details', alert.reason || 'Multiple parameters outside baseline.');
        if (raw.latitude && raw.longitude) {
          this.setText('w-alert-loc', `${raw.latitude.toFixed(3)}, ${raw.longitude.toFixed(3)}`);
        }
      }
    }

    // Page 6: Diagnostics
    const now = new Date();
    this.setText('w-sys-packet', now.toLocaleTimeString());
    this.setText('w-sys-latency', `${latencyMs} ms`);
  }

  setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  setSubRisk(id, level) {
    const el = document.getElementById(id);
    if (el) {
      const lvl = level || 'LOW';
      el.textContent = lvl === 'LOW' ? 'Low' : lvl.replace(/_/g, ' ');
      el.className = lvl === 'CRITICAL' ? 'text-danger' : lvl === 'ELEVATED' || lvl === 'EARLY_WARNING' ? 'text-warning' : 'text-muted';
    }
  }

  renderSparkline(svgId, data, minVal, maxVal) {
    const svg = document.getElementById(svgId);
    if (!svg || data.length < 2) return;

    const width = 100;
    const height = 24;
    const range = maxVal - minVal || 1;
    const step = width / (data.length - 1);

    const points = data.map((val, idx) => {
      const clamped = Math.max(minVal, Math.min(maxVal, val));
      const x = idx * step;
      const y = height - ((clamped - minVal) / range) * (height - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    svg.innerHTML = `
      <polyline
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-linejoin="round"
        points="${points}"
      />
    `;
  }
}
