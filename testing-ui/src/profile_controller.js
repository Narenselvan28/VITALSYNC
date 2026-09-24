/**
 * VITALSYNC: Profile Controller for Simulation Lab
 * Manages personalized patient health profile switching,
 * active condition contexts, and decision transparency.
 */

import { api } from './api.js';

export class ProfileController {
  constructor(onProfileChanged) {
    this.onProfileChanged = onProfileChanged;
    this.currentProfile = null;

    this._cacheDom();
    this._bindEvents();
  }

  _cacheDom() {
    this.verEl = document.getElementById('lab-prof-ver');
    this.statusEl = document.getElementById('lab-prof-status');
    this.ageSexEl = document.getElementById('lab-prof-age-sex');
    this.htWtEl = document.getElementById('lab-prof-ht-wt');
    this.conditionsEl = document.getElementById('lab-prof-conditions');
    this.medsEl = document.getElementById('lab-prof-meds');
    this.contextsEl = document.getElementById('lab-prof-contexts');
    this.sourcesEl = document.getElementById('lab-prof-decision-sources');
    this.noticeEl = document.getElementById('lab-prof-notice');
    this.presetBtns = document.querySelectorAll('.btn-profile-preset');
  }

  _bindEvents() {
    this.presetPresets = {
      healthy: {
        age: 30,
        sex: 'M',
        height_cm: 175,
        weight_kg: 70,
        conditions: ['none'],
        medications: [],
        medication_context: 'UNKNOWN'
      },
      asthma: {
        age: 35,
        sex: 'F',
        height_cm: 165,
        weight_kg: 62,
        conditions: ['asthma'],
        medications: ['albuterol inhaler'],
        medication_context: 'albuterol inhaler'
      },
      cardiovascular: {
        age: 58,
        sex: 'M',
        height_cm: 172,
        weight_kg: 80,
        conditions: ['cardiovascular'],
        medications: ['beta-blocker'],
        medication_context: 'beta-blocker'
      },
      hypertension: {
        age: 52,
        sex: 'M',
        height_cm: 178,
        weight_kg: 84,
        conditions: ['hypertension'],
        medications: ['amlodipine'],
        medication_context: 'amlodipine'
      },
      diabetes: {
        age: 48,
        sex: 'F',
        height_cm: 160,
        weight_kg: 68,
        conditions: ['diabetes'],
        medications: ['metformin'],
        medication_context: 'metformin'
      },
      copd: {
        age: 65,
        sex: 'M',
        height_cm: 168,
        weight_kg: 65,
        conditions: ['copd'],
        medications: ['tiotropium inhaler'],
        medication_context: 'tiotropium inhaler'
      },
      asthma_htn: {
        age: 54,
        sex: 'F',
        height_cm: 162,
        weight_kg: 71,
        conditions: ['asthma', 'hypertension'],
        medications: ['inhaler', 'ace-inhibitor'],
        medication_context: 'inhaler, ace-inhibitor'
      }
    };

    this.presetBtns.forEach((btn) => {
      btn.addEventListener('click', async () => {
        const pKey = btn.getAttribute('data-profile');
        const pData = this.presetPresets[pKey];
        if (!pData) return;

        this.presetBtns.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');

        const activeDevId = document.getElementById('txt-device-id')?.value || 'SIM-001';

        try {
          const res = await api.updateProfile({
            device_id: activeDevId,
            ...pData
          });

          // Also keep ESP32-001 in sync so user-ui watchface reflects the exact profile
          if (activeDevId !== 'ESP32-001') {
            await api.updateProfile({
              device_id: 'ESP32-001',
              ...pData
            });
          }

          this.updateDisplay({
            patient_profile: res.profile,
            active_condition_contexts: res.active_contexts || [],
            decision_sources: ['REFERENCE_THRESHOLD', 'PERSONAL_BASELINE']
          });

          if (this.onProfileChanged) {
            await this.onProfileChanged(res);
          }
        } catch (e) {
          console.error('[ProfileController] Failed to switch profile:', e);
        }
      });
    });
  }

  async loadInitialProfile() {
    try {
      const activeDevId = document.getElementById('txt-device-id')?.value || 'SIM-001';
      const data = await api.fetchProfile(activeDevId);
      if (data && data.profile) {
        this.updateDisplay({
          patient_profile: data.profile,
          active_condition_contexts: data.active_contexts || [],
          decision_sources: ['REFERENCE_THRESHOLD', 'PERSONAL_BASELINE']
        });
      }
    } catch (e) {
      console.warn('[ProfileController] Failed to load initial profile:', e);
    }
  }

  updateDisplay(payload) {
    if (!payload) return;

    const prof = payload.patient_profile || {};
    const contexts = payload.active_condition_contexts || [];
    const sources = payload.decision_sources || [];
    const notices = payload.special_notices || [];

    if (prof.profile_version && this.verEl) {
      this.verEl.textContent = `v${prof.profile_version}`;
    }

    if (this.statusEl) {
      const st = prof.baseline_status || 'LEARNING';
      this.statusEl.textContent = st;
      this.statusEl.className = `badge-profile-status ${st === 'LEARNING' ? '' : 'active'}`;
    }

    if (this.ageSexEl && prof.age) {
      this.ageSexEl.textContent = `${prof.age} · ${prof.sex || 'M'}`;
    }

    if (this.htWtEl && prof.height_cm) {
      this.htWtEl.textContent = `${Math.round(prof.height_cm)} cm · ${Math.round(prof.weight_kg)} kg`;
    }

    if (this.conditionsEl) {
      const conds = prof.conditions || ['none'];
      this.conditionsEl.textContent = conds.map((c) => c.replace(/_/g, ' ')).join(', ') || 'No known condition';
    }

    if (this.medsEl) {
      const medCtx = prof.medication_context || 'UNKNOWN';
      this.medsEl.textContent = medCtx !== 'UNKNOWN' ? `${medCtx} (Context)` : 'None reported (Context only)';
    }

    // Active Contexts
    if (this.contextsEl) {
      if (contexts.length > 0) {
        this.contextsEl.innerHTML = contexts
          .map((ctx) => `<span class="chip-ctx">${ctx.replace(/_monitoring|_/g, ' ')}</span>`)
          .join('');
      } else {
        this.contextsEl.innerHTML = '<span class="chip-ctx">nominal_monitoring</span>';
      }
    }

    // Decision Sources
    if (this.sourcesEl) {
      if (sources.length > 0) {
        this.sourcesEl.innerHTML = sources
          .map((src) => `<span class="chip-src">${src.replace(/_/g, ' ')}</span>`)
          .join('');
      } else {
        this.sourcesEl.innerHTML = '<span class="chip-src">NOMINAL TRACKING</span>';
      }
    }

    // Special notices
    if (this.noticeEl) {
      if (notices.length > 0) {
        this.noticeEl.textContent = `ℹ️ ${notices[0]}`;
        this.noticeEl.classList.remove('hidden');
      } else {
        this.noticeEl.classList.add('hidden');
      }
    }
  }
}
