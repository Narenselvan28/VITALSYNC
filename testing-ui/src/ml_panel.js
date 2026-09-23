/**
 * AAROGYA-SHIELD: ML Results & Feature Attribution Panel
 * Renders the multi-model prediction matrix and
 * "Why did the model change?" contributing feature list directly from backend response.
 */

export class MLPanelController {
  constructor() {
    this.overallBadge = document.getElementById('chip-overall-risk');
    this.overallLvlText = document.getElementById('txt-overall-lvl');
    this.overallScoreText = document.getElementById('txt-overall-score');
    this.overallTrendText = document.getElementById('txt-overall-trend');
    this.whyContainer = document.getElementById('why-features-list');
  }

  updateDisplay(payload) {
    if (!payload) return;

    const preds = payload.ml_predictions || payload.predictions || {};
    const escalation = payload.escalation || {};
    const overall = preds.overall_health_risk || preds.overall || {};
    const features = payload.features || {};

    const overallLevel = escalation.escalated_level || overall.risk_level || 'LOW';
    const overallScore = overall.score !== undefined ? overall.score : 0.08;

    // Overall Chip
    if (this.overallLvlText) this.overallLvlText.textContent = overallLevel.replace('_', ' ');
    if (this.overallScoreText) this.overallScoreText.textContent = overallScore.toFixed(2);
    if (this.overallBadge) {
      this.overallBadge.className = 'overall-risk-badge font-mono ' + this._getLevelClass(overallLevel);
    }

    const trend = features.hr_trend > 0.3 ? '↑ INCREASING' : features.hr_trend < -0.3 ? '↓ DECREASING' : '→ STABLE';
    if (this.overallTrendText) this.overallTrendText.textContent = trend;

    // Model Rows
    this._updateModelRow('resp', preds.respiratory_risk);
    this._updateModelRow('oxy', preds.oxygenation_anomaly);
    this._updateModelRow('heat', preds.heat_stress_risk);
    this._updateModelRow('fatigue', preds.fatigue_strain_risk);
    this._updateModelRow('env', preds.environmental_exposure_risk);
    this._updateModelRow('gen', preds.general_health_anomaly);

    // Why Did The Model Change? (Contributing Features)
    this._renderWhyExplanations(preds.why_explanations || payload.contributing_features || []);
  }

  _updateModelRow(key, modelData) {
    const scoreEl = document.getElementById(`ml-score-${key}`);
    const lvlEl = document.getElementById(`ml-lvl-${key}`);
    if (!modelData) return;

    if (scoreEl && modelData.score !== undefined) {
      scoreEl.textContent = modelData.score.toFixed(2);
    }

    if (lvlEl && modelData.risk_level) {
      lvlEl.textContent = modelData.risk_level.replace('_', ' ');
      lvlEl.className = 'badge-lvl ' + this._getLevelBadgeClass(modelData.risk_level);
    }
  }

  _renderWhyExplanations(explanations) {
    if (!this.whyContainer) return;

    if (!Array.isArray(explanations) || explanations.length === 0) {
      this.whyContainer.innerHTML = `
        <div class="why-item">
          <span class="why-desc text-muted">Feature attribution not provided by model.</span>
        </div>
      `;
      return;
    }

    const html = explanations.map((item) => {
      const impact = item.impact || (item.weight ? `+${item.weight.toFixed(2)}` : '+0.00');
      const feature = item.feature || item.name || 'Parameter';
      const detail = item.detail || item.description || '';
      const isGreen = impact === '+0.00' || impact === '0.00';

      return `
        <div class="why-item">
          <span class="why-weight ${isGreen ? 'text-green' : 'text-amber'}">${impact}</span>
          <span class="why-desc">${feature}</span>
          ${detail ? `<span class="why-detail text-muted">${detail}</span>` : ''}
        </div>
      `;
    }).join('');

    this.whyContainer.innerHTML = html;
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
