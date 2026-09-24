/**
 * VITALSYNC: Timeline & Personal Baseline Display
 * Renders real backend risk events and baseline statistics.
 * Memory capped to 300 entries for Raspberry Pi 4 stability.
 */

export class TimelineController {
  constructor(maxEntries = 300) {
    this.maxEntries = maxEntries;
    this.entries = [];
    this.tbody = document.getElementById('timeline-body');
  }

  addEntryFromPayload(payload) {
    if (!payload) return;

    const preds = payload.ml_predictions || payload.predictions || {};
    const escalation = payload.escalation || {};
    const overall = preds.overall_health_risk || preds.overall || {};
    const spike = payload.spike || {};

    const level = escalation.escalated_level || overall.risk_level || 'LOW';
    const score = overall.score !== undefined ? overall.score : 0.08;
    const timeStr = payload.timestamp ? new Date(payload.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();

    // Check if a dedicated spike or recovery event was emitted
    if (spike.events_emitted && spike.events_emitted.length > 0) {
      for (const spEv of spike.events_emitted) {
        if (spEv.type === 'SPIKE_EVENT') {
          this.addEntry({
            time: spEv.timestamp ? new Date(spEv.timestamp).toLocaleTimeString() : timeStr,
            level: 'SPIKE',
            score: '0.50',
            details: `⚡ ${spEv.domain} spike: ${spEv.previous} → ${spEv.current} (Rapid change detected)`,
          });
        } else if (spEv.type === 'RECOVERY_EVENT') {
          this.addEntry({
            time: spEv.timestamp ? new Date(spEv.timestamp).toLocaleTimeString() : timeStr,
            level: 'RECOVERED',
            score: '0.10',
            details: `✓ ${spEv.domain} recovery: ${spEv.current} back near baseline`,
          });
        }
      }
    }

    let details = 'All physiological parameters within personal baseline';
    if (escalation.reasons && escalation.reasons.length > 0) {
      details = escalation.reasons[0];
    } else if (preds.why_explanations && preds.why_explanations.length > 0) {
      details = preds.why_explanations[0].feature;
    }

    this.addEntry({
      time: timeStr,
      level,
      score: score.toFixed(2),
      details,
    });

    // Update Personal Baseline card from backend response
    this.updateBaselineSummary(payload.baseline_summary, payload.raw_sensors || payload.sensor_data);
  }

  addEntry(entry) {
    this.entries.unshift(entry);
    if (this.entries.length > this.maxEntries) {
      this.entries.pop();
    }
    this._renderTable();
  }

  _renderTable() {
    if (!this.tbody) return;

    if (this.entries.length === 0) {
      this.tbody.innerHTML = '<tr><td colspan="4" class="text-muted">Awaiting backend inference events...</td></tr>';
      return;
    }

    const html = this.entries.slice(0, 30).map((row) => {
      const lvlClass = this._getLevelClass(row.level);
      return `
        <tr>
          <td>${row.time}</td>
          <td><span class="badge-lvl ${lvlClass}">${row.level.replace('_', ' ')}</span></td>
          <td><strong>${row.score}</strong></td>
          <td class="text-muted">${row.details}</td>
        </tr>
      `;
    }).join('');

    this.tbody.innerHTML = html;
  }

  updateBaselineSummary(baseline, rawSensors = {}) {
    if (!baseline) return;

    const hr = baseline.heart_rate || {};
    const spo2 = baseline.spo2 || {};
    const temp = baseline.body_temperature || {};
    const mq = baseline.mq45 || {};

    // HR
    const hrBase = hr.baseline_mean !== undefined ? hr.baseline_mean.toFixed(1) : '72.0';
    const hrCurr = hr.current !== undefined ? hr.current.toFixed(1) : (rawSensors.heart_rate || 74).toFixed(1);
    const hrRel = hr.relative_deviation !== undefined ? (hr.relative_deviation * 100).toFixed(1) : '0.0';
    const hrSign = hrRel >= 0 ? `+${hrRel}%` : `${hrRel}%`;
    const bHrEl = document.getElementById('b-hr-vals');
    if (bHrEl) bHrEl.textContent = `base ${hrBase} · current ${hrCurr} · ${hrSign}`;

    // SpO2
    const spo2Base = spo2.baseline_mean !== undefined ? spo2.baseline_mean.toFixed(1) : '98.0';
    const spo2Curr = spo2.current !== undefined ? spo2.current.toFixed(1) : (rawSensors.spo2 || 98).toFixed(1);
    const spo2Rel = spo2.relative_deviation !== undefined ? (spo2.relative_deviation * 100).toFixed(1) : '0.0';
    const spo2Sign = spo2Rel >= 0 ? `+${spo2Rel}%` : `${spo2Rel}%`;
    const bSpo2El = document.getElementById('b-spo2-vals');
    if (bSpo2El) bSpo2El.textContent = `base ${spo2Base} · current ${spo2Curr} · ${spo2Sign}`;

    // Body Temp
    const tempBase = temp.baseline_mean !== undefined ? temp.baseline_mean.toFixed(1) : '36.7';
    const tempCurr = temp.current !== undefined ? temp.current.toFixed(1) : (rawSensors.body_temperature || 36.7).toFixed(1);
    const tempDiff = temp.difference !== undefined ? temp.difference.toFixed(1) : '0.0';
    const tempSign = tempDiff >= 0 ? `+${tempDiff}°C` : `${tempDiff}°C`;
    const bTempEl = document.getElementById('b-temp-vals');
    if (bTempEl) bTempEl.textContent = `base ${tempBase}°C · current ${tempCurr}°C · ${tempSign}`;

    // MQ-45
    const mqBase = mq.baseline_mean !== undefined ? mq.baseline_mean.toFixed(0) : '180';
    const mqCurr = mq.current !== undefined ? mq.current.toFixed(0) : (rawSensors.mq45 || 180).toFixed(0);
    const bMqEl = document.getElementById('b-mq-vals');
    if (bMqEl) bMqEl.textContent = `base ${mqBase} · current ${mqCurr}`;
  }

  _getLevelClass(lvl) {
    switch (lvl) {
      case 'CRITICAL': return 'lvl-critical';
      case 'ELEVATED':
      case 'SPIKE': return 'lvl-elevated';
      case 'EARLY_WARNING': return 'lvl-early';
      case 'RECOVERED': return 'lvl-low';
      default: return 'lvl-low';
    }
  }
}
