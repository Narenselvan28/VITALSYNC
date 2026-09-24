/**
 * VITALSYNC: Developer Debug & Telemetry Inspector
 * Inspects real-time API transactions, HTTP status, roundtrip latency,
 * model artifacts status, and raw JSON request/response payloads.
 */

export class DebugPanelController {
  constructor() {
    this.endpointEl = document.getElementById('dbg-endpoint');
    this.httpEl = document.getElementById('dbg-http');
    this.latencyEl = document.getElementById('dbg-latency');
    this.modelEl = document.getElementById('dbg-model');
    this.featuresEl = document.getElementById('dbg-features');
    this.wsEl = document.getElementById('dbg-ws');
    this.preReq = document.getElementById('pre-last-req');
    this.preResp = document.getElementById('pre-last-resp');

    this._bindCopyButtons();
  }

  _bindCopyButtons() {
    document.getElementById('btn-copy-req')?.addEventListener('click', () => {
      if (this.preReq) navigator.clipboard.writeText(this.preReq.textContent);
    });

    document.getElementById('btn-copy-resp')?.addEventListener('click', () => {
      if (this.preResp) navigator.clipboard.writeText(this.preResp.textContent);
    });
  }

  updateFromTelemetry({ endpoint, status, latencyMs, request, response, isOnline }) {
    if (this.endpointEl && endpoint) this.endpointEl.textContent = endpoint;

    if (this.httpEl && status) {
      this.httpEl.textContent = `${status} ${status === 200 ? 'OK' : 'ERR'}`;
      this.httpEl.className = status === 200 ? 'text-green' : 'text-red font-bold';
    }

    if (this.latencyEl && latencyMs !== undefined) {
      this.latencyEl.textContent = `${latencyMs} ms`;
    }

    if (request && this.preReq) {
      this.preReq.textContent = JSON.stringify(request, null, 2);
    }

    if (response && this.preResp) {
      this.preResp.textContent = JSON.stringify(response, null, 2);
    }

    // Extract features count & model version if present in response
    if (response) {
      if (response.features && this.featuresEl) {
        this.featuresEl.textContent = Object.keys(response.features).length;
      }
      const modelVer = response.ml_predictions?.model_version || response.model_version;
      if (modelVer && this.modelEl) {
        this.modelEl.textContent = `XGBoost v1 (${modelVer})`;
      }
    }
  }

  updateWsStatus(status) {
    if (this.wsEl) {
      this.wsEl.textContent = status;
      this.wsEl.className = status === 'CONNECTED' ? 'text-green' : 'text-red font-bold';
    }
  }
}
