/**
 * VITALSYNC: Caretaker Alert Controller
 * Displays live caretaker notifications and handles
 * real backend acknowledgment via POST /api/alerts/{id}/acknowledge.
 */

import { api } from './api.js';

export class CaretakerAlertController {
  constructor(onAlertAcknowledged) {
    this.onAlertAcknowledged = onAlertAcknowledged;
    this.currentAlert = null;

    this.emptyView = document.getElementById('alert-card-empty');
    this.activeView = document.getElementById('alert-card-active');
    this.statusBadge = document.getElementById('lbl-alert-badge');
    this.headlineEl = document.getElementById('lbl-alert-headline');
    this.messageEl = document.getElementById('lbl-alert-message');
    this.factorsEl = document.getElementById('lbl-alert-factors');
    this.idEl = document.getElementById('lbl-alert-id');
    this.timeEl = document.getElementById('lbl-alert-time');
    this.ackBtn = document.getElementById('btn-ack-alert');

    this._bindEvents();
  }

  _bindEvents() {
    this.ackBtn?.addEventListener('click', async () => {
      if (!this.currentAlert || !this.currentAlert.alert_id) return;
      this.ackBtn.disabled = true;
      this.ackBtn.textContent = 'ACKNOWLEDGING...';

      try {
        await api.acknowledgeAlert(this.currentAlert.alert_id);
        this.currentAlert.acknowledged = true;
        this.updateDisplay(null);
        if (this.onAlertAcknowledged) {
          this.onAlertAcknowledged(this.currentAlert);
        }
      } catch (err) {
        console.error('[Caretaker] Acknowledge error:', err);
      } finally {
        this.ackBtn.disabled = false;
        this.ackBtn.textContent = '✓ ACKNOWLEDGE ALERT';
      }
    });
  }

  updateDisplay(alert) {
    this.currentAlert = alert;

    if (!alert || alert.acknowledged || alert.message === 'No active alerts') {
      this.emptyView?.classList.remove('hidden');
      this.activeView?.classList.add('hidden');
      if (this.statusBadge) {
        this.statusBadge.textContent = 'NO ALERT';
        this.statusBadge.className = 'alert-status-badge font-mono';
      }
      return;
    }

    // Active alert
    this.emptyView?.classList.add('hidden');
    this.activeView?.classList.remove('hidden');

    const lvl = alert.risk_level || 'EARLY_WARNING';
    if (this.statusBadge) {
      this.statusBadge.textContent = lvl.replace('_', ' ');
      this.statusBadge.className = 'alert-status-badge font-mono ' + (lvl === 'CRITICAL' ? 'text-red font-bold' : 'text-amber font-bold');
    }

    if (this.headlineEl) this.headlineEl.textContent = `${lvl.replace('_', ' ')} · ${alert.risk_type || 'PHYSIOLOGICAL'}`;
    if (this.messageEl) this.messageEl.textContent = alert.message || 'Abnormal parameter deviation.';

    const factors = Array.isArray(alert.contributing_parameters) && alert.contributing_parameters.length > 0
      ? alert.contributing_parameters.join('; ')
      : 'Multiple baseline deviations';
    if (this.factorsEl) this.factorsEl.textContent = `Factors: ${factors}`;

    if (this.idEl) this.idEl.textContent = alert.alert_id || 'ALT-SYNC';
    const timeStr = alert.timestamp ? new Date(alert.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
    if (this.timeEl) this.timeEl.textContent = timeStr;
  }
}
