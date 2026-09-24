/**
 * VITALSYNC: In-App Automated Test Suite Runner
 * Executes the 6 acceptance test scenarios sequentially against the real FastAPI backend.
 * Measures real latency and asserts backend response structures.
 */

import { api } from './api.js';
import { PRESETS } from './simulator.js';

export class TestRunnerController {
  constructor(simulator, onTestStepComplete) {
    this.simulator = simulator;
    this.onTestStepComplete = onTestStepComplete;

    this.card = document.getElementById('card-test-runner');
    this.resultsBody = document.getElementById('test-results-body');
    this.summaryLabel = document.getElementById('lbl-runner-summary');
    this.runAllBtn = document.getElementById('btn-run-all-tests');

    this._bindEvents();
  }

  _bindEvents() {
    this.runAllBtn?.addEventListener('click', () => {
      this.runAllScenarios();
    });
  }

  async runAllScenarios() {
    if (this.card) this.card.classList.remove('hidden');
    if (this.resultsBody) this.resultsBody.innerHTML = '';
    if (this.runAllBtn) this.runAllBtn.disabled = true;

    const testPlan = [
      {
        id: 1,
        name: 'NORMAL PHYSIOLOGY',
        preset: PRESETS.normal,
        verify: (res) => {
          const lvl = res.escalation?.escalated_level || res.ml_predictions?.overall_health_risk?.risk_level;
          return lvl === 'LOW';
        },
      },
      {
        id: 2,
        name: 'EARLY RESPIRATORY WARNING',
        preset: PRESETS.early_resp,
        verify: (res) => {
          const respLvl = res.ml_predictions?.respiratory_risk?.risk_level;
          const overallLvl = res.escalation?.escalated_level;
          return respLvl === 'EARLY_WARNING' || overallLvl === 'EARLY_WARNING' || respLvl === 'ELEVATED';
        },
      },
      {
        id: 3,
        name: 'HEAT STRESS EXPOSURE',
        preset: PRESETS.heat,
        verify: (res) => {
          const heatLvl = res.ml_predictions?.heat_stress_risk?.risk_level;
          return heatLvl === 'ELEVATED' || heatLvl === 'CRITICAL' || heatLvl === 'EARLY_WARNING';
        },
      },
      {
        id: 4,
        name: 'ENVIRONMENTAL GAS EXPOSURE',
        preset: PRESETS.env,
        verify: (res) => {
          const envLvl = res.ml_predictions?.environmental_exposure_risk?.risk_level;
          return envLvl === 'ELEVATED' || envLvl === 'CRITICAL' || envLvl === 'EARLY_WARNING';
        },
      },
      {
        id: 5,
        name: 'CRITICAL MULTI-PARAM + ALERT',
        preset: PRESETS.critical,
        verify: (res) => {
          const overallLvl = res.escalation?.escalated_level || res.ml_predictions?.overall_health_risk?.risk_level;
          const hasAlert = res.active_alert !== null && res.active_alert !== undefined;
          return overallLvl === 'CRITICAL' && hasAlert;
        },
      },
      {
        id: 6,
        name: 'PHYSIOLOGICAL RECOVERY SEQUENCE',
        preset: PRESETS.recovery,
        verify: (res) => {
          const overallScore = res.ml_predictions?.overall_health_risk?.score;
          return overallScore < 0.60;
        },
      },
    ];

    let passedCount = 0;

    for (const test of testPlan) {
      if (this.summaryLabel) {
        this.summaryLabel.textContent = `RUNNING TEST ${test.id} OF ${testPlan.length}: ${test.name}...`;
      }

      this.simulator.applyValues(test.preset);
      const startTime = performance.now();
      let status = 'PASS';
      let httpCode = 200;
      let latency = 0;
      let outcome = '';

      try {
        const payload = this.simulator.getPayload();
        const res = await api.sendSimulatorReading(payload);
        latency = Math.round(performance.now() - startTime);
        httpCode = api.lastStatus || 200;

        const isVerified = test.verify(res);
        if (isVerified) {
          status = 'PASS';
          passedCount++;
          const lvl = res.escalation?.escalated_level || res.ml_predictions?.overall_health_risk?.risk_level || 'OK';
          const score = res.ml_predictions?.overall_health_risk?.score?.toFixed(2) || '0.00';
          outcome = `Verified Level: ${lvl} (Score: ${score})`;
        } else {
          status = 'FAIL';
          outcome = 'Assertion condition not met by model response.';
        }

        // Notify parent app
        if (this.onTestStepComplete) {
          this.onTestStepComplete(res, latency);
        }
      } catch (err) {
        status = 'FAIL';
        httpCode = 500;
        latency = Math.round(performance.now() - startTime);
        outcome = err.message;
      }

      this._appendTestRow({
        status,
        name: test.name,
        httpCode,
        latency,
        outcome,
      });

      // Brief delay between automated runs
      await new Promise((r) => setTimeout(r, 250));
    }

    if (this.summaryLabel) {
      this.summaryLabel.textContent = `TEST RUN COMPLETED: ${passedCount}/${testPlan.length} PASSED (100% REAL BACKEND)`;
    }
    if (this.runAllBtn) this.runAllBtn.disabled = false;
  }

  _appendTestRow({ status, name, httpCode, latency, outcome }) {
    if (!this.resultsBody) return;
    const tr = document.createElement('tr');
    const isPass = status === 'PASS';
    tr.innerHTML = `
      <td><span class="${isPass ? 'badge-pass' : 'badge-fail'} font-mono">${status}</span></td>
      <td><strong>${name}</strong></td>
      <td>HTTP ${httpCode}</td>
      <td>${latency} ms</td>
      <td class="text-muted">${outcome}</td>
    `;
    this.resultsBody.appendChild(tr);
  }
}
