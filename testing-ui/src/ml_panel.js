export class MLPanelController {
  constructor() {
    this.overallBadge = document.getElementById('chip-overall-risk');
    this.overallLvlText = document.getElementById('txt-overall-lvl');
    this.overallScoreText = document.getElementById('txt-overall-score');
    this.overallTrendText = document.getElementById('txt-overall-trend');

    this.rcBadge = document.getElementById('chip-root-cause');
    this.rcPrimaryText = document.getElementById('txt-root-cause-primary');
    this.rcConfText = document.getElementById('txt-root-cause-conf');

    this.ansWhatChanged = document.getElementById('ans-what-changed');
    this.ansGenuine = document.getElementById('ans-genuine-verdict');
    this.ansContext = document.getElementById('ans-contributing-context');
    this.ansMultimodal = document.getElementById('ans-multimodal-verdict');
    this.ansPersistence = document.getElementById('ans-temporal-verdict');
    this.ansRecovery = document.getElementById('ans-recovery-verdict');
    this.ansAlert = document.getElementById('ans-alert-verdict');
    this.ansSummary = document.getElementById('ans-reasoning-summary');

    this.supportingChips = document.getElementById('rc-supporting-chips');
    this.contradictingChips = document.getElementById('rc-contradicting-chips');

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

    if (this.overallLvlText) {
      this.overallLvlText.textContent = overallLevel === 'LOW' ? 'Low' : overallLevel.replace(/_/g, ' ');
    }
    if (this.overallScoreText) {
      this.overallScoreText.textContent = Number(overallScore).toFixed(2);
    }
    if (this.overallBadge) {
      this.overallBadge.className = 'badge-risk font-mono ' + (overallLevel === 'CRITICAL' ? 'badge-danger' : overallLevel === 'ELEVATED' || overallLevel === 'EARLY_WARNING' ? 'text-warning' : '');
    }

    const trend = features.hr_trend > 0.3 ? 'Rising' : features.hr_trend < -0.3 ? 'Falling' : 'Stable';
    if (this.overallTrendText) this.overallTrendText.textContent = trend;

    this.updateDomainRow('hr', domains.heart_rate_anomaly || preds.heart_rate_risk);
    this.updateDomainRow('oxy', domains.oxygenation_anomaly || preds.oxygenation_anomaly);
    this.updateDomainRow('resp', domains.respiratory_risk || preds.respiratory_risk);
    this.updateDomainRow('heat', domains.thermal_strain || preds.thermal_risk || preds.heat_stress_risk);
    this.updateDomainRow('env', domains.environmental_exposure || preds.environmental_risk);
    this.updateDomainRow('fatigue', domains.activity_strain || preds.activity_risk || preds.fatigue_strain_risk);
    this.updateDomainRow('fall', domains.fall_event || preds.fall_risk);
    this.updateDomainRow('gen', domains.general_anomaly || preds.general_health_anomaly);

    this.updateSensorQuality(qualities, features);

    const primaryCause = rc.primary || 'Normal physiology';
    if (this.rcPrimaryText) this.rcPrimaryText.textContent = primaryCause.replace(/_/g, ' ');
    if (this.rcConfText) this.rcConfText.classList.add('hidden');

    if (this.ansWhatChanged && clinical.what_changed) this.ansWhatChanged.textContent = clinical.what_changed;
    if (this.ansGenuine && clinical.genuine_verdict) this.ansGenuine.textContent = clinical.genuine_verdict;
    if (this.ansContext && clinical.contributing_context) this.ansContext.textContent = clinical.contributing_context;
    if (this.ansMultimodal && clinical.multimodal_verdict) this.ansMultimodal.textContent = clinical.multimodal_verdict;
    if (this.ansPersistence && clinical.temporal_verdict) this.ansPersistence.textContent = clinical.temporal_verdict;
    if (this.ansRecovery && clinical.recovery_verdict) this.ansRecovery.textContent = clinical.recovery_verdict;
    if (this.ansAlert && clinical.alert_verdict) this.ansAlert.textContent = clinical.alert_verdict;
    if (this.ansSummary && clinical.reasoning_summary) this.ansSummary.textContent = clinical.reasoning_summary;

    const supporting = fused.evidence || rc.supporting_evidence || [];
    const contradicting = fused.contradicting_evidence || rc.contradicting_evidence || [];
    this.renderEvidenceChips(supporting, contradicting);
  }

  updateDomainRow(key, domainData) {
    const scoreEl = document.getElementById(`ml-score-${key}`);
    const lvlEl = document.getElementById(`ml-lvl-${key}`);
    const reasonEl = document.getElementById(`ml-reason-${key}`);
    if (!domainData) return;

    if (scoreEl && domainData.score !== undefined) {
      scoreEl.textContent = Number(domainData.score).toFixed(2);
    }

    const lvl = domainData.level || domainData.risk_level || (domainData.is_confirmed ? 'CRITICAL' : domainData.is_candidate ? 'ELEVATED' : 'LOW');
    if (lvlEl) {
      lvlEl.textContent = lvl === 'LOW' ? 'Low' : lvl.replace(/_/g, ' ');
      lvlEl.className = 'badge-tag ' + (lvl === 'CRITICAL' ? 'badge-danger' : lvl === 'ELEVATED' || lvl === 'EARLY_WARNING' ? 'text-warning' : '');
    }

    if (reasonEl) {
      reasonEl.textContent = domainData.reason || (domainData.is_confirmed ? 'Fall confirmed' : domainData.is_candidate ? 'Fall candidate' : 'Baseline');
    }
  }

  updateSensorQuality(qualities, features) {
    const ppgQ = features.ppg_quality !== undefined ? Math.round(features.ppg_quality * 100) : 96;
    if (this.sqPpg) {
      const q = qualities.ppg || (ppgQ >= 75 ? 'Good' : ppgQ >= 50 ? 'Fair' : 'Poor');
      this.sqPpg.textContent = `${q} (${ppgQ}%)`;
    }

    if (this.sqAdxl) {
      const adxlAvail = features.adxl_available !== false;
      this.sqAdxl.textContent = adxlAvail ? 'Good' : 'Offline';
    }

    if (this.sqNtc) {
      this.sqNtc.textContent = features.is_transient_thermal ? 'Transient' : 'Good';
    }

    if (this.sqMq45) {
      const mq = features.mq45 || 180;
      this.sqMq45.textContent = mq > 500 ? `Elevated (${Math.round(mq)})` : `Good (${Math.round(mq)})`;
    }

    if (this.sqGps) {
      const gpsFix = features.gps_fix !== false && features.latitude !== null;
      this.sqGps.textContent = gpsFix ? 'Fix' : 'Searching';
    }

    if (this.sqWeatherMode) {
      const weather = features.weather_context || {};
      this.sqWeatherMode.textContent = weather.mode === 'LOCAL_SENSOR_ONLY' ? 'Local' : 'Augmented';
    }
  }

  renderEvidenceChips(supporting, contradicting) {
    if (this.supportingChips) {
      if (Array.isArray(supporting) && supporting.length > 0) {
        this.supportingChips.innerHTML = supporting
          .map((item) => `<span class="chip-subtle">${this.escape(item)}</span>`)
          .join('');
      } else {
        this.supportingChips.innerHTML = '<span class="text-xs text-muted">All parameters within baseline limits.</span>';
      }
    }

    if (this.contradictingChips) {
      if (Array.isArray(contradicting) && contradicting.length > 0) {
        this.contradictingChips.innerHTML = contradicting
          .map((item) => `<span class="chip-subtle">${this.escape(item)}</span>`)
          .join('');
      } else {
        this.contradictingChips.innerHTML = '<span class="text-xs text-muted">No conflicting indicators observed.</span>';
      }
    }
  }

  escape(str) {
    return String(str).replace(/[&<>"']/g, (m) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    }[m]));
  }
}
