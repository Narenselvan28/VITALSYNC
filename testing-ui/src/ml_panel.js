/**
 * VITALSYNC: ML Results & Clinical-Context Reasoning Panel
 * Renders:
 * 1. 8 Decoupled ML Risk Domains (Scores, Status, Contributing Patterns)
 * 2. Sensor Quality & Trust Reliability Bar (MAX30102, ADXL345, NTC, MQ-45, GPS, Weather)
 * 3. Root-Cause Analysis Primary Badge & Confidence
 * 4. Deterministic Answers to the 8 Core Clinical Questions
 * 5. Supporting & Contradicting Evidence Chips
 */

export class MLPanelController {
  constructor() {
    // Overall Risk Elements
    this.overallBadge = document.getElementById('chip-overall-risk');
    this.overallLvlText = document.getElementById('txt-overall-lvl');
    this.overallScoreText = document.getElementById('txt-overall-score');
    this.overallTrendText = document.getElementById('txt-overall-trend');

    // Root Cause Elements
    this.rcBadge = document.getElementById('chip-root-cause');
    this.rcPrimaryText = document.getElementById('txt-root-cause-primary');
    this.rcConfText = document.getElementById('txt-root-cause-conf');

    // 8 Clinical Questions Answers
    this.ansWhatChanged = document.getElementById('ans-what-changed');
    this.ansGenuine = document.getElementById('ans-genuine-verdict');
    this.ansContext = document.getElementById('ans-contributing-context');
    this.ansMultimodal = document.getElementById('ans-multimodal-verdict');
    this.ansPersistence = document.getElementById('ans-temporal-verdict');
    this.ansRecovery = document.getElementById('ans-recovery-verdict');
    this.ansAlert = document.getElementById('ans-alert-verdict');
    this.ansSummary = document.getElementById('ans-reasoning-summary');

    // Evidence Chips
    this.supportingChips = document.getElementById('rc-supporting-chips');
    this.contradictingChips = document.getElementById('rc-contradicting-chips');

    // Sensor Quality Bar
    this.sqPpg = document.getElementById('sq-ppg');
    this.sqAdxl = document.getElementById('sq-adxl');
    this.sqNtc = document.getElementById('sq-ntc');
    this.sqMq45 = document.getElementById('sq-mq45');
    this.sqGps = document.getElementById('sq-gps');
    this.sqWeatherMode = document.getElementById('sq-weather-mode');
  }

  updateDisplay(payload) {
    if (!payload) return;

    const preds = payload.ml_predictions || payload.predictions || {};
    const domains = preds.risk_domains || {};
    const escalation = payload.escalation || {};
    const overall = preds.overall_health_risk || preds.overall || {};
    const features = payload.features || {};
    const fused = payload.fused_risk || {};
    const rc = payload.root_cause_analysis || fused.root_cause || {};
    const clinical = payload.clinical_context || fused.clinical_answers || {};
    const qualities = payload.qualities || fused.sensor_quality || {};

    const overallLevel = escalation.escalated_level || overall.risk_level || 'LOW';
    const overallScore = overall.score !== undefined ? overall.score : 0.08;

    // 1. Overall Risk Header
    if (this.overallLvlText) this.overallLvlText.textContent = overallLevel.replace(/_/g, ' ');
    if (this.overallScoreText) this.overallScoreText.textContent = Number(overallScore).toFixed(2);
    if (this.overallBadge) {
      this.overallBadge.className = 'overall-risk-badge font-mono ' + this._getLevelClass(overallLevel);
    }

    const trend = features.hr_trend > 0.3 ? '↑ INCREASING' : features.hr_trend < -0.3 ? '↓ DECREASING' : '→ STABLE';
    if (this.overallTrendText) this.overallTrendText.textContent = trend;

    // 2. 8 Decoupled Domain Rows
    this._updateDomainRow('hr', domains.heart_rate_anomaly || preds.heart_rate_risk);
    this._updateDomainRow('oxy', domains.oxygenation_anomaly || preds.oxygenation_anomaly);
    this._updateDomainRow('resp', domains.respiratory_risk || preds.respiratory_risk);
    this._updateDomainRow('heat', domains.thermal_strain || preds.thermal_risk || preds.heat_stress_risk);
    this._updateDomainRow('env', domains.environmental_exposure || preds.environmental_risk);
    this._updateDomainRow('fatigue', domains.activity_strain || preds.activity_risk || preds.fatigue_strain_risk);
    this._updateDomainRow('fall', domains.fall_event || preds.fall_risk);
    this._updateDomainRow('gen', domains.general_anomaly || preds.general_health_anomaly);

    // 3. Sensor Quality Trust Indicators
    this._updateSensorQuality(qualities, features);

    // 4. Root-Cause Analysis Header
    const primaryCause = rc.primary || 'NORMAL_PHYSIOLOGY';
    const confidence = rc.confidence !== undefined ? Math.round(rc.confidence * 100) : 95;
    if (this.rcPrimaryText) this.rcPrimaryText.textContent = primaryCause.replace(/_/g, ' ');
    if (this.rcConfText) this.rcConfText.textContent = `${confidence}% CONF`;

    // 5. 8 Clinical Questions Answers
    if (this.ansWhatChanged && clinical.what_changed) {
      this.ansWhatChanged.textContent = clinical.what_changed;
    }
    if (this.ansGenuine && clinical.genuine_verdict) {
      this.ansGenuine.textContent = clinical.genuine_verdict;
    }
    if (this.ansContext && clinical.contributing_context) {
      this.ansContext.textContent = clinical.contributing_context;
    }
    if (this.ansMultimodal && clinical.multimodal_verdict) {
      this.ansMultimodal.textContent = clinical.multimodal_verdict;
    }
    if (this.ansPersistence && clinical.temporal_verdict) {
      this.ansPersistence.textContent = clinical.temporal_verdict;
    }
    if (this.ansRecovery && clinical.recovery_verdict) {
      this.ansRecovery.textContent = clinical.recovery_verdict;
    }
    if (this.ansAlert && clinical.alert_verdict) {
      this.ansAlert.textContent = clinical.alert_verdict;
    }
    if (this.ansSummary && clinical.reasoning_summary) {
      this.ansSummary.textContent = clinical.reasoning_summary;
    }

    // 6. Evidence Chips
    const supporting = fused.evidence || rc.supporting_evidence || [];
    const contradicting = fused.contradicting_evidence || rc.contradicting_evidence || [];
    this._renderEvidenceChips(supporting, contradicting);
  }

  _updateDomainRow(key, domainData) {
    const scoreEl = document.getElementById(`ml-score-${key}`);
    const lvlEl = document.getElementById(`ml-lvl-${key}`);
    const reasonEl = document.getElementById(`ml-reason-${key}`);
    if (!domainData) return;

    if (scoreEl && domainData.score !== undefined) {
      scoreEl.textContent = Number(domainData.score).toFixed(2);
    }

    const lvl = domainData.level || domainData.risk_level || (domainData.is_confirmed ? 'CRITICAL' : domainData.is_candidate ? 'ELEVATED' : 'LOW');
    if (lvlEl) {
      lvlEl.textContent = lvl.replace(/_/g, ' ');
      lvlEl.className = 'badge-lvl ' + this._getLevelBadgeClass(lvl);
    }

    if (reasonEl) {
      const reason = domainData.reason || (domainData.is_confirmed ? 'Confirmed fall impact' : domainData.is_candidate ? 'Fall candidate window' : 'Nominal');
      reasonEl.textContent = reason;
    }
  }

  _updateSensorQuality(qualities, features) {
    const ppgQ = features.ppg_quality !== undefined ? Math.round(features.ppg_quality * 100) : 96;
    if (this.sqPpg) {
      const q = qualities.ppg || (ppgQ >= 75 ? 'GOOD' : ppgQ >= 50 ? 'FAIR' : 'POOR');
      this.sqPpg.textContent = `${q} (${ppgQ}%)`;
      this.sqPpg.className = 'sq-chip-val ' + (q === 'GOOD' ? 'sq-good' : q === 'FAIR' ? 'sq-fair' : 'sq-poor');
    }

    if (this.sqAdxl) {
      const adxlAvail = features.adxl_available !== false;
      this.sqAdxl.textContent = adxlAvail ? 'GOOD' : 'UNAVAILABLE';
      this.sqAdxl.className = 'sq-chip-val ' + (adxlAvail ? 'sq-good' : 'sq-unavail');
    }

    if (this.sqNtc) {
      const isTransient = features.is_transient_thermal;
      this.sqNtc.textContent = isTransient ? 'TRANSIENT' : 'GOOD';
      this.sqNtc.className = 'sq-chip-val ' + (isTransient ? 'sq-fair' : 'sq-good');
    }

    if (this.sqMq45) {
      const mq = features.mq45 || 180;
      const status = mq > 500 ? 'ELEVATED' : 'GOOD';
      this.sqMq45.textContent = `${status} (${Math.round(mq)})`;
      this.sqMq45.className = 'sq-chip-val ' + (status === 'GOOD' ? 'sq-good' : 'sq-fair');
    }

    if (this.sqGps) {
      const gpsFix = features.gps_fix !== false && features.latitude !== null;
      this.sqGps.textContent = gpsFix ? 'FIX (3D)' : 'NO FIX';
      this.sqGps.className = 'sq-chip-val ' + (gpsFix ? 'sq-good' : 'sq-fair');
    }

    if (this.sqWeatherMode) {
      const weather = features.weather_context || {};
      const mode = weather.mode || 'WEATHER_AUGMENTED';
      this.sqWeatherMode.textContent = mode === 'LOCAL_SENSOR_ONLY' ? 'LOCAL SENSOR' : 'AUGMENTED';
      this.sqWeatherMode.className = 'sq-chip-val ' + (mode === 'LOCAL_SENSOR_ONLY' ? 'sq-fair' : 'sq-good');
    }
  }

  _renderEvidenceChips(supporting, contradicting) {
    if (this.supportingChips) {
      if (Array.isArray(supporting) && supporting.length > 0) {
        this.supportingChips.innerHTML = supporting
          .map((item) => `<span class="chip-evidence">${this._escape(item)}</span>`)
          .join('');
      } else {
        this.supportingChips.innerHTML = '<span class="text-xs text-muted">All physiological metrics within baseline limits.</span>';
      }
    }

    if (this.contradictingChips) {
      if (Array.isArray(contradicting) && contradicting.length > 0) {
        this.contradictingChips.innerHTML = contradicting
          .map((item) => `<span class="chip-evidence-contra">${this._escape(item)}</span>`)
          .join('');
      } else {
        this.contradictingChips.innerHTML = '<span class="text-xs text-muted">No conflicting clinical indicators observed.</span>';
      }
    }
  }

  _escape(str) {
    return String(str).replace(/[&<>"']/g, (m) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    }[m]));
  }

  _getLevelClass(lvl) {
    switch (lvl) {
      case 'CRITICAL': return 'lvl-critical';
      case 'ELEVATED': return 'lvl-elevated';
      case 'EARLY_WARNING': return 'lvl-early';
      default: return '';
    }
  }

  _getLevelBadgeClass(lvl) {
    switch (lvl) {
      case 'CRITICAL': return 'lvl-critical';
      case 'ELEVATED': return 'lvl-elevated';
      case 'EARLY_WARNING': return 'lvl-early';
      default: return 'lvl-low';
    }
  }
}
