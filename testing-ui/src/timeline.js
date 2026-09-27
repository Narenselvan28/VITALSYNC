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

    if (spike.events_emitted && spike.events_emitted.length > 0) {
      for (const spEv of spike.events_emitted) {
        if (spEv.type === 'SPIKE_EVENT') {
          this.addEntry({
            time: spEv.timestamp ? new Date(spEv.timestamp).toLocaleTimeString() : timeStr,
            level: 'SPIKE',
            score: '0.50',
            details: `${spEv.domain} spike: ${spEv.previous} → ${spEv.current}`,
          });
        } else if (spEv.type === 'RECOVERY_EVENT') {
          this.addEntry({
            time: spEv.timestamp ? new Date(spEv.timestamp).toLocaleTimeString() : timeStr,
            level: 'RECOVERED',
            score: '0.10',
            details: `${spEv.domain} recovered: ${spEv.current} back near baseline`,
          });
        }
      }
    }

    let details = 'All parameters tracking within baseline limits';
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

    this.updateBaselineSummary(payload.baseline_summary, payload.raw_sensors || payload.sensor_data);
  }

  addEntry(entry) {
    this.entries.unshift(entry);
    if (this.entries.length > this.maxEntries) {
      this.entries.pop();
    }
    this.renderTable();
  }

  renderTable() {
    if (!this.tbody) return;

    if (this.entries.length === 0) {
      this.tbody.innerHTML = '<tr><td colspan="4" class="text-muted">Awaiting backend inference events...</td></tr>';
      return;
    }

    const html = this.entries.slice(0, 30).map((row) => {
      const isCritical = row.level === 'CRITICAL';
      const isWarning = row.level === 'ELEVATED' || row.level === 'EARLY_WARNING' || row.level === 'SPIKE';
      const badgeClass = isCritical ? 'badge-danger' : isWarning ? 'text-warning' : '';
      return `
        <tr>
          <td>${row.time}</td>
          <td><span class="badge-tag font-mono ${badgeClass}">${row.level === 'LOW' ? 'Normal' : row.level.replace(/_/g, ' ')}</span></td>
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

    const hrEl = document.getElementById('b-hr-vals');
    if (hrEl) {
      const baseMean = hr.mean ? Math.round(hr.mean) : 72;
      const cur = rawSensors.heart_rate ? Math.round(rawSensors.heart_rate) : baseMean;
      hrEl.textContent = `base ${baseMean} · current ${cur}`;
    }

    const spo2El = document.getElementById('b-spo2-vals');
    if (spo2El) {
      const baseMean = spo2.mean ? Math.round(spo2.mean) : 98;
      const cur = rawSensors.spo2 ? Math.round(rawSensors.spo2) : baseMean;
      spo2El.textContent = `base ${baseMean}% · current ${cur}%`;
    }

    const tempEl = document.getElementById('b-temp-vals');
    if (tempEl) {
      const baseMean = temp.mean ? temp.mean.toFixed(1) : '36.7';
      const cur = rawSensors.body_temperature ? rawSensors.body_temperature.toFixed(1) : baseMean;
      tempEl.textContent = `base ${baseMean}°C · current ${cur}°C`;
    }

    const mqEl = document.getElementById('b-mq-vals');
    if (mqEl) {
      const baseMean = mq.mean ? Math.round(mq.mean) : 180;
      const cur = rawSensors.mq45 ? Math.round(rawSensors.mq45) : baseMean;
      mqEl.textContent = `base ${baseMean} · current ${cur}`;
    }
  }
}
