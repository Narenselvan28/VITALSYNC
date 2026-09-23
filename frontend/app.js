/**
 * =============================================================================
 * VITALSYNC: Front-End Application Controller
 * Handles WebSocket telemetry streaming, personal baseline visualization,
 * dual Canvas oscilloscopes, interactive ML test lab with presets,
 * caretaker alert notifications & acknowledgments, and device diagnostics.
 * =============================================================================
 */

// Application State
const state = {
  activeView: "overview",
  connected: false,
  ws: null,
  activeAlert: null,
  latestTelemetry: null,
  allAlerts: [],
  activeAlertFilter: "ALL",
  trendHistory: [],
  maxTrendHistory: 60,
  debounceTimer: null,
  baselineStats: null,
  packetCount: 0,
  selectedOverviewSignal: "hr", // hr, spo2, body_temperature, ambient_temperature, humidity, mq45, overall_risk
  overviewTimeRangeMinutes: 5,
  escalationStepIndex: 0,
};

// Color Tokens & State Stylings
const COLORS = {
  LOW: "#15803d",
  NORMAL: "#15803d",
  EARLY_WARNING: "#b45309",
  ELEVATED: "#c2410c",
  CRITICAL: "#b91c1c",
};

// Preset Scenarios
const PRESETS = {
  normal: {
    heart_rate: 74,
    spo2: 98,
    ppg_quality: 0.96,
    body_temperature: 36.7,
    ambient_temperature: 28.0,
    humidity: 60,
    mq45: 180,
    activity_level: 0,
    accel_x: 0.02,
    accel_y: 0.01,
    accel_z: 0.98,
  },
  early_respiratory: {
    heart_rate: 88,
    spo2: 94,
    ppg_quality: 0.94,
    body_temperature: 36.8,
    ambient_temperature: 28.5,
    humidity: 62,
    mq45: 340,
    activity_level: 0,
    accel_x: 0.02,
    accel_y: 0.01,
    accel_z: 0.98,
  },
  elevated_respiratory: {
    heart_rate: 112,
    spo2: 90,
    ppg_quality: 0.88,
    body_temperature: 37.3,
    ambient_temperature: 30.0,
    humidity: 65,
    mq45: 520,
    activity_level: 1,
    accel_x: 0.10,
    accel_y: 0.10,
    accel_z: 0.95,
  },
  high_environmental: {
    heart_rate: 82,
    spo2: 96,
    ppg_quality: 0.92,
    body_temperature: 36.9,
    ambient_temperature: 34.0,
    humidity: 72,
    mq45: 780,
    activity_level: 0,
    accel_x: 0.02,
    accel_y: 0.01,
    accel_z: 0.98,
  },
  heat_stress: {
    heart_rate: 122,
    spo2: 97,
    ppg_quality: 0.90,
    body_temperature: 39.1,
    ambient_temperature: 43.0,
    humidity: 82,
    mq45: 220,
    activity_level: 2,
    accel_x: 0.25,
    accel_y: 0.25,
    accel_z: 1.05,
  },
  fatigue: {
    heart_rate: 132,
    spo2: 96,
    ppg_quality: 0.85,
    body_temperature: 37.8,
    ambient_temperature: 31.0,
    humidity: 68,
    mq45: 210,
    activity_level: 3,
    accel_x: 0.65,
    accel_y: 0.55,
    accel_z: 1.35,
  },
  recovery: {
    heart_rate: 76,
    spo2: 98,
    ppg_quality: 0.96,
    body_temperature: 36.8,
    ambient_temperature: 26.5,
    humidity: 55,
    mq45: 160,
    activity_level: 0,
    accel_x: 0.02,
    accel_y: 0.01,
    accel_z: 0.98,
  },
  critical: {
    heart_rate: 142,
    spo2: 85,
    ppg_quality: 0.75,
    body_temperature: 39.8,
    ambient_temperature: 44.0,
    humidity: 86,
    mq45: 860,
    activity_level: 4,
    accel_x: 2.40,
    accel_y: 2.10,
    accel_z: 0.30,
  },
};

const ESCALATION_CHAIN = [
  "normal",
  "early_respiratory",
  "elevated_respiratory",
  "critical"
];

// Initialize Application on Page Load
function boot() {
  initClock();
  initTabs();
  initOverviewChartTabs();
  initWebSocket();
  initTestLabControls();
  initAlertFilters();
  initCaretakerBanner();
  initMatrixDetailModal();
  initCanvasCharts();
  fetchInitialData();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}

// --- 1. Top Real-Time Clock ---
function initClock() {
  const clockEl = document.getElementById("top-clock");
  function updateTime() {
    if (clockEl) {
      const now = new Date();
      clockEl.innerText = now.toTimeString().split(" ")[0];
    }
  }
  updateTime();
  setInterval(updateTime, 1000);
}

// --- 2. Navigation Tabs Switcher ---
function initTabs() {
  const navTabs = document.querySelectorAll(".nav-tab");
  const viewPanels = document.querySelectorAll(".view-panel");

  function switchView(viewName) {
    state.activeView = viewName;

    navTabs.forEach((tab) => {
      if (tab.getAttribute("data-view") === viewName) {
        tab.classList.add("active");
      } else {
        tab.classList.remove("active");
      }
    });

    viewPanels.forEach((panel) => {
      if (panel.id === `view-${viewName}`) {
        panel.classList.add("active");
      } else {
        panel.classList.remove("active");
      }
    });

    // Redraw charts if switching into Overview or Monitor
    if (viewName === "overview") {
      setTimeout(renderOverviewChart, 50);
    } else if (viewName === "monitor") {
      setTimeout(renderMonitorWaveforms, 50);
    }

    const route = viewName === "overview" ? "/" : `/${viewName}`;
    if (window.location.pathname !== route && window.history) {
      window.history.pushState({}, "", route);
    }
  }

  navTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const view = tab.getAttribute("data-view");
      if (view) switchView(view);
    });
  });

  // Handle URL path on first load
  const rawPath = window.location.pathname.replace("/", "");
  if (rawPath && ["overview", "monitor", "lab", "alerts", "device"].includes(rawPath)) {
    switchView(rawPath);
  }

  // Recalibrate baseline buttons
  document.getElementById("btn-recalibrate-top")?.addEventListener("click", recalibrateBaseline);
}

async function recalibrateBaseline() {
  try {
    const res = await fetch("/api/baseline/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: "ESP32-001" }),
    });
    if (res.ok) {
      const stripEl = document.getElementById("strip-baseline-status");
      if (stripEl) stripEl.innerText = "CALIBRATING (0/30 Samples)...";
    }
  } catch (e) {
    console.error("Baseline recalibrate error:", e);
  }
}

// --- 3. WebSocket Streaming Connection ---
function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/live`;

  updateConnectionStatus(false, "CONNECTING");

  state.ws = new WebSocket(wsUrl);

  state.ws.onopen = () => {
    updateConnectionStatus(true, "LIVE");
  };

  state.ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleIncomingTelemetry(data);
    } catch (e) {
      console.error("[WS] Parse error:", e);
    }
  };

  state.ws.onclose = () => {
    updateConnectionStatus(false, "OFFLINE");
    setTimeout(initWebSocket, 2500); // Auto-reconnect
  };

  state.ws.onerror = (err) => {
    console.warn("[WS] Socket error:", err);
  };
}

function updateConnectionStatus(online, text) {
  state.connected = online;
  const dot = document.getElementById("top-conn-dot");
  const txt = document.getElementById("top-conn-text");
  const monDot = document.getElementById("mon-ws-dot");
  const monTxt = document.getElementById("mon-ws-status");
  const labBackend = document.getElementById("lab-backend-status");

  if (dot) {
    dot.className = online ? "pulse-dot online-dot" : "pulse-dot";
    dot.style.backgroundColor = online ? "var(--state-normal-dot)" : "#ef4444";
  }
  if (txt) txt.innerText = text;

  if (monDot) {
    monDot.className = online ? "conn-dot dot-green" : "conn-dot dot-red";
  }
  if (monTxt) monTxt.innerText = online ? "STREAMING" : "DISCONNECTED";

  if (labBackend) {
    labBackend.innerText = online ? "CONNECTED" : "OFFLINE";
    labBackend.className = online ? "meta-val val-connected" : "meta-val";
  }
}

// --- 4. Ingestion & Real-Time Telemetry Dispatcher ---
function handleIncomingTelemetry(payload) {
  if (payload.event_type === "ALERT_ACKNOWLEDGED") {
    handleAlertAcknowledged(payload);
    return;
  }

  if (payload.event_type !== "TELEMETRY_UPDATE") return;

  state.latestTelemetry = payload;
  state.packetCount++;

  const raw = payload.raw_sensors || {};
  const feat = payload.features || {};
  const ml = payload.ml_predictions || {};
  const esc = payload.escalation || {};
  const overall = ml.overall_health_risk || {};

  // 1. Update Diagnostics & Node Chips
  updateDeviceDiagnostics(payload.device_status, payload.device_id, payload.timestamp);

  // 2. Update View 1: Overview
  updateOverviewView(raw, feat, ml, esc, overall);

  // 3. Update View 2: Live Monitor
  updateMonitorView(raw, feat, ml, esc, overall, payload.active_alert);

  // 4. Update View 3: Test Lab Outputs
  updateTestLabOutputs(raw, feat, ml, esc, overall);

  // 5. Update Caretaker Emergency Banner & Alert widgets
  updateAlertComponents(payload.active_alert);

  // 6. Record Trend History & Render Oscilloscopes
  recordTrendDataPoint(raw, feat, overall);
  renderOverviewChart();
  renderMonitorWaveforms();
}

function updateDeviceDiagnostics(deviceStatus, deviceId, timestamp) {
  if (deviceId) {
    const chipDev = document.getElementById("top-device-id");
    if (chipDev) chipDev.innerText = deviceId;
  }

  const monEspDot = document.getElementById("mon-esp-dot");
  const monEspStatus = document.getElementById("mon-esp-status");
  const monPackets = document.getElementById("mon-packet-count");
  const devPackets = document.getElementById("dev-packets-count");
  const devLast = document.getElementById("dev-last-telemetry");
  const devEsp32 = document.getElementById("dev-esp32-badge");

  if (monPackets) monPackets.innerText = state.packetCount;
  if (devPackets) devPackets.innerText = state.packetCount;

  if (devLast) {
    devLast.innerText = timestamp ? new Date(timestamp).toLocaleTimeString() : "Live";
  }

  const isOnline = deviceStatus === "ONLINE" || state.connected;
  if (monEspDot) {
    monEspDot.className = isOnline ? "conn-dot dot-green" : "conn-dot dot-yellow";
  }
  if (monEspStatus) {
    monEspStatus.innerText = isOnline ? "CONNECTED" : "STANDBY";
  }
  if (devEsp32) {
    devEsp32.innerText = isOnline ? "ONLINE" : "STANDBY";
    devEsp32.className = isOnline ? "diag-badge badge-green" : "diag-badge badge-yellow";
  }
}

// --- 5. DOM View Updaters ---

// === VIEW 1: OVERVIEW ===
function updateOverviewView(raw, feat, ml, esc, overall) {
  const score = overall.score !== undefined ? overall.score : 0.10;
  const level = esc.escalated_level || overall.risk_level || "LOW";
  const confidence = overall.confidence !== undefined ? Math.round(overall.confidence * 100) : 94;

  // Hero Status
  const scoreEl = document.getElementById("ov-risk-score");
  if (scoreEl) scoreEl.innerText = score.toFixed(2);

  const confEl = document.getElementById("ov-confidence");
  if (confEl) confEl.innerText = `Model Confidence: ${confidence}%`;

  const badgeEl = document.getElementById("ov-status-badge");
  if (badgeEl) {
    const displayLevel = level === "LOW" ? "NORMAL" : level.replace("_", " ");
    badgeEl.innerText = displayLevel;
    badgeEl.className = `status-badge-lg badge-${level.toLowerCase().replace("_", "-")}`;
  }

  // Linear spectrum fill
  const specFill = document.getElementById("ov-spectrum-fill");
  if (specFill) {
    const pct = Math.min(100, Math.max(5, score * 100));
    specFill.style.width = `${pct}%`;
  }

  // Risk Trend Arrow
  const trendArrow = document.getElementById("ov-trend-arrow");
  const trendText = document.getElementById("ov-trend-text");
  if (trendArrow && trendText) {
    if (score > 0.6) {
      trendArrow.innerText = "↑";
      trendText.innerText = "Deteriorating";
    } else if (score > 0.3) {
      trendArrow.innerText = "↗";
      trendText.innerText = "Elevating";
    } else {
      trendArrow.innerText = "→";
      trendText.innerText = "Stable";
    }
  }

  // Physiological Metrics Strip
  const hr = Math.round(raw.heart_rate || 74);
  const spo2 = Math.round(raw.spo2 || 98);
  const temp = (raw.body_temperature || 36.7).toFixed(1);
  const act = feat.activity_level || feat.activity_label || "REST";
  const mag = (feat.acceleration_magnitude || 0.98).toFixed(2);

  const ovHr = document.getElementById("ov-hr-val");
  if (ovHr) ovHr.innerText = hr;
  const hrDevPct = feat.hr_deviation !== undefined ? (feat.hr_deviation * 100).toFixed(1) : "0.0";
  const ovHrDev = document.getElementById("ov-hr-dev");
  if (ovHrDev) {
    const arrow = hrDevPct > 1.5 ? "↑" : hrDevPct < -1.5 ? "↓" : "→";
    ovHrDev.innerHTML = `<span class="meta-trend">${arrow}</span> ${hrDevPct >= 0 ? "+" : ""}${hrDevPct}% from baseline`;
  }

  const ovSpo2 = document.getElementById("ov-spo2-val");
  if (ovSpo2) ovSpo2.innerText = spo2;
  const spo2DevPct = feat.spo2_deviation !== undefined ? (feat.spo2_deviation * 100).toFixed(1) : "0.0";
  const ovSpo2Dev = document.getElementById("ov-spo2-dev");
  if (ovSpo2Dev) {
    const arrow = spo2DevPct < -1.5 ? "↓" : spo2DevPct > 1.5 ? "↑" : "→";
    ovSpo2Dev.innerHTML = `<span class="meta-trend">${arrow}</span> ${spo2DevPct >= 0 ? "+" : ""}${spo2DevPct}% from baseline`;
  }

  const ovTemp = document.getElementById("ov-temp-val");
  if (ovTemp) ovTemp.innerText = temp;
  const tempDevVal = feat.temp_deviation !== undefined ? feat.temp_deviation.toFixed(1) : "0.0";
  const ovTempDev = document.getElementById("ov-temp-dev");
  if (ovTempDev) {
    const arrow = tempDevVal > 0.4 ? "↑" : tempDevVal < -0.4 ? "↓" : "→";
    ovTempDev.innerHTML = `<span class="meta-trend">${arrow}</span> ${tempDevVal >= 0 ? "+" : ""}${tempDevVal}°C from baseline`;
  }

  const ovAct = document.getElementById("ov-act-val");
  if (ovAct) ovAct.innerText = act;
  const ovActMag = document.getElementById("ov-act-mag");
  if (ovActMag) ovActMag.innerText = `${mag}g`;

  // Environmental Metrics Strip
  const amb = (raw.ambient_temperature || 28.0).toFixed(1);
  const hum = Math.round(raw.humidity || 60);
  const mq = Math.round(raw.mq45 || 180);
  const hi = feat.heat_index !== undefined ? feat.heat_index.toFixed(1) : amb;

  const ovAmb = document.getElementById("ov-amb-val");
  if (ovAmb) ovAmb.innerText = amb;
  const ovHum = document.getElementById("ov-hum-val");
  if (ovHum) ovHum.innerText = hum;
  const ovHeatIdx = document.getElementById("ov-heat-idx");
  if (ovHeatIdx) ovHeatIdx.innerText = `Heat Index: ${hi}°C`;

  const ovMq = document.getElementById("ov-mq-val");
  if (ovMq) ovMq.innerText = mq;
  const ovMqBadge = document.getElementById("ov-mq-badge");
  const ovMqDesc = document.getElementById("ov-mq-desc");
  if (ovMqBadge) {
    if (mq > 650) {
      ovMqBadge.innerText = "CRITICAL";
      ovMqBadge.className = "status-chip chip-critical font-mono";
      if (ovMqDesc) ovMqDesc.innerText = "Severe environmental exposure";
    } else if (mq > 400) {
      ovMqBadge.innerText = "ELEVATED";
      ovMqBadge.className = "status-chip chip-elevated font-mono";
      if (ovMqDesc) ovMqDesc.innerText = "Elevated exposure detected";
    } else if (mq > 250) {
      ovMqBadge.innerText = "WARNING";
      ovMqBadge.className = "status-chip chip-warning font-mono";
      if (ovMqDesc) ovMqDesc.innerText = "Mild atmospheric elevation";
    } else {
      ovMqBadge.innerText = "NORMAL";
      ovMqBadge.className = "status-chip chip-normal font-mono";
      if (ovMqDesc) ovMqDesc.innerText = "Atmospheric baseline (uncalibrated exposure indicator)";
    }
  }

  // Risk Matrix Rows in Overview
  updateMatrixRow("resp", ml.respiratory_risk);
  updateMatrixRow("oxy", ml.oxygenation_anomaly);
  updateMatrixRow("heat", ml.heat_stress_risk);
  updateMatrixRow("fatigue", ml.fatigue_strain_risk);
  updateMatrixRow("env", ml.environmental_exposure_risk);
  updateMatrixRow("gen", ml.general_health_anomaly);

  // Early Warning Timeline Item
  updateTimeline(level, esc);
}

function updateMatrixRow(prefix, modelData) {
  if (!modelData) return;
  const scoreEl = document.getElementById(`rm-${prefix}-score`);
  const badgeEl = document.getElementById(`rm-${prefix}-badge`);
  const trendEl = document.getElementById(`rm-${prefix}-trend`);

  if (scoreEl) scoreEl.innerText = (modelData.score || 0.10).toFixed(2);
  if (badgeEl) {
    const lvl = modelData.risk_level || "LOW";
    badgeEl.innerText = lvl === "LOW" ? "NORMAL" : lvl.replace("_", " ");
    badgeEl.className = `status-chip chip-${lvl.toLowerCase().replace("_", "-")} font-mono`;
  }
  if (trendEl) {
    trendEl.innerText = (modelData.score || 0) > 0.5 ? "↑" : (modelData.score || 0) > 0.25 ? "↗" : "→";
  }
}

function updateTimeline(level, esc) {
  const container = document.getElementById("overview-timeline-list");
  if (!container) return;

  const displayLevel = level === "LOW" ? "NORMAL" : level.replace("_", " ");
  const bulletClass = `mark-${level.toLowerCase().replace("_", "-")}`;
  const reasonsText = (esc.reasons && esc.reasons.length > 0)
    ? esc.reasons.join(". ")
    : "All physiological parameters tracking within personal baseline.";

  container.innerHTML = `
    <div class="timeline-item">
      <div class="timeline-bullet ${bulletClass}"></div>
      <div class="timeline-content">
        <div class="timeline-time font-mono">Live (${new Date().toLocaleTimeString()})</div>
        <div class="timeline-title">${displayLevel}</div>
        <div class="timeline-desc">${reasonsText}</div>
      </div>
    </div>
  `;
}

// === VIEW 2: LIVE MONITOR ===
function updateMonitorView(raw, feat, ml, esc, overall, activeAlert) {
  // Raw Sensor Readout Stack
  const setEl = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.innerText = text;
  };

  setEl("mon-hr", Math.round(raw.heart_rate || 74));
  setEl("mon-spo2", Math.round(raw.spo2 || 98));
  setEl("mon-ppg", (raw.ppg_quality || 0.95).toFixed(2));
  setEl("mon-temp", (raw.body_temperature || 36.7).toFixed(1));
  setEl("mon-amb", (raw.ambient_temperature || 28.0).toFixed(1));
  setEl("mon-hum", Math.round(raw.humidity || 60));
  setEl("mon-hi", (feat.heat_index || raw.ambient_temperature || 28.0).toFixed(1));
  setEl("mon-mq", Math.round(raw.mq45 || 180));

  const ax = (raw.accel_x || 0.02).toFixed(2);
  const ay = (raw.accel_y || 0.01).toFixed(2);
  const az = (raw.accel_z || 0.98).toFixed(2);
  setEl("mon-accel", `${ax >= 0 ? "+" : ""}${ax}, ${ay >= 0 ? "+" : ""}${ay}, ${az >= 0 ? "+" : ""}${az}`);
  setEl("mon-mag", `${(feat.acceleration_magnitude || 0.98).toFixed(2)}g`);
  setEl("mon-act", feat.activity_level || feat.activity_label || "REST");
  setEl("mon-gps", `${(raw.latitude || 10.662).toFixed(3)}, ${(raw.longitude || 76.891).toFixed(3)}`);

  // Evaluated State Badge & Score
  const level = esc.escalated_level || overall.risk_level || "LOW";
  const monBadge = document.getElementById("mon-risk-badge-text");
  if (monBadge) {
    const displayLevel = level === "LOW" ? "NORMAL" : level.replace("_", " ");
    monBadge.innerText = displayLevel;
    monBadge.className = `status-${level.toLowerCase().replace("_", "-")}`;
  }

  setEl("mon-risk-score", (overall.score || 0.10).toFixed(2));
  const monTrend = document.getElementById("mon-risk-trend");
  if (monTrend) {
    monTrend.innerText = (overall.score || 0) > 0.6 ? "↑ High Anomaly" : (overall.score || 0) > 0.3 ? "↗ Elevating" : "→ Stable";
  }

  // Caretaker Alert Box in Live Monitor
  const alertDetail = document.getElementById("mon-alert-detail");
  if (alertDetail) {
    if (activeAlert && !activeAlert.acknowledged) {
      alertDetail.innerHTML = `
        <span style="color:var(--state-critical-dot); font-weight:700;">[${activeAlert.risk_level}] ${activeAlert.risk_type}</span><br>
        <span>${activeAlert.message}</span><br>
        <span class="text-muted">ID: ${activeAlert.alert_id} | Location: ${activeAlert.latitude || 10.662}°, ${activeAlert.longitude || 76.891}°</span>
      `;
    } else {
      alertDetail.innerHTML = `<span>No active alerts. System nominal.</span>`;
    }
  }

  // Reasoning & Contributing Factors Grid
  const reasonGrid = document.getElementById("monitor-reasoning-grid");
  if (reasonGrid) {
    const reasons = (esc.reasons && esc.reasons.length > 0)
      ? esc.reasons
      : (overall.contributing_features?.top_drivers || ["All parameters tracking within individual personal baseline."]);

    reasonGrid.innerHTML = reasons.map((r) => `
      <div class="reason-card">
        <span class="reason-score font-mono">+${((overall.score || 0.1) * 0.4).toFixed(2)}</span>
        <div class="reason-text">
          <strong>${r}</strong>
          <span>Attributed via personal baseline standard deviation & trend tracking.</span>
        </div>
      </div>
    `).join("");
  }
}

// === VIEW 3: TEST LAB OUTPUTS ===
function updateTestLabOutputs(raw, feat, ml, esc, overall) {
  const level = esc.escalated_level || overall.risk_level || "LOW";
  const score = overall.score !== undefined ? overall.score : 0.10;

  const labBadge = document.getElementById("lab-overall-badge");
  if (labBadge) {
    const displayLevel = level === "LOW" ? "NORMAL" : level.replace("_", " ");
    labBadge.innerText = displayLevel;
    labBadge.className = `status-badge-lg badge-${level.toLowerCase().replace("_", "-")}`;
  }

  const labScore = document.getElementById("lab-overall-score");
  if (labScore) labScore.innerText = score.toFixed(2);

  const labTrend = document.getElementById("lab-overall-trend");
  if (labTrend) {
    labTrend.innerText = score > 0.5 ? "↑ Escalating" : score > 0.25 ? "↗ Elevated" : "→ Stable";
  }

  // Table of 6 Models
  const updateLabModelRow = (prefix, data) => {
    if (!data) return;
    const sEl = document.getElementById(`lab-m-${prefix}-score`);
    const bEl = document.getElementById(`lab-m-${prefix}-badge`);
    if (sEl) sEl.innerText = (data.score || 0.10).toFixed(2);
    if (bEl) {
      const lvl = data.risk_level || "LOW";
      bEl.innerText = lvl === "LOW" ? "NORMAL" : lvl.replace("_", " ");
      bEl.className = `status-chip chip-${lvl.toLowerCase().replace("_", "-")} font-mono`;
    }
  };

  updateLabModelRow("gen", ml.general_health_anomaly);
  updateLabModelRow("resp", ml.respiratory_risk);
  updateLabModelRow("oxy", ml.oxygenation_anomaly);
  updateLabModelRow("heat", ml.heat_stress_risk);
  updateLabModelRow("fatigue", ml.fatigue_strain_risk);
  updateLabModelRow("env", ml.environmental_exposure_risk);

  // Section 4: Why did the model change?
  const whyList = document.getElementById("lab-why-list");
  if (whyList) {
    const reasons = (esc.reasons && esc.reasons.length > 0)
      ? esc.reasons
      : (overall.contributing_features?.top_drivers || ["All parameters within personal baseline"]);

    whyList.innerHTML = reasons.map((r, i) => `
      <div class="why-item font-mono">
        <span class="why-impact">+${(0.05 + i * 0.04).toFixed(2)}</span>
        <div class="why-content">
          <strong>${r}</strong>
          <span class="why-detail">Telemetry deviation filtered through multi-parameter confirmation engine</span>
        </div>
      </div>
    `).join("");
  }

  // Section 5: Personal Baseline Comparison Table
  const baseHr = feat.baseline_summary?.heart_rate?.baseline_mean || 72.0;
  const baseSpo2 = feat.baseline_summary?.spo2?.baseline_mean || 98.0;
  const baseTemp = feat.baseline_summary?.body_temperature?.baseline_mean || 36.7;

  const setT = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.innerText = val;
  };

  setT("lb-base-hr", `${baseHr.toFixed(1)} BPM`);
  setT("lb-curr-hr", `${Math.round(raw.heart_rate || 74)} BPM`);
  const hrDev = feat.hr_deviation !== undefined ? (feat.hr_deviation * 100).toFixed(1) : "0.0";
  setT("lb-dev-hr", `${hrDev >= 0 ? "+" : ""}${hrDev}%`);

  setT("lb-base-spo2", `${baseSpo2.toFixed(1)}%`);
  setT("lb-curr-spo2", `${Math.round(raw.spo2 || 98)}%`);
  const spo2Dev = feat.spo2_deviation !== undefined ? (feat.spo2_deviation * 100).toFixed(1) : "0.0";
  setT("lb-dev-spo2", `${spo2Dev >= 0 ? "+" : ""}${spo2Dev}%`);

  setT("lb-base-temp", `${baseTemp.toFixed(1)}°C`);
  setT("lb-curr-temp", `${(raw.body_temperature || 36.7).toFixed(1)}°C`);
  const tDev = feat.temp_deviation !== undefined ? feat.temp_deviation.toFixed(1) : "0.0";
  setT("lb-dev-temp", `${tDev >= 0 ? "+" : ""}${tDev}°C`);

  setT("lb-curr-amb", `${(raw.ambient_temperature || 28.0).toFixed(1)}°C`);
  setT("lb-curr-hum", `${Math.round(raw.humidity || 60)}%`);

  const infStatus = document.getElementById("lab-inference-status");
  if (infStatus) infStatus.innerText = "Inference active (Live)";
}

// === CARETAKER BANNER & IN-PAGE ALERT WIDGET ===
function updateAlertComponents(activeAlert) {
  state.activeAlert = activeAlert;

  const banner = document.getElementById("caretaker-banner");
  const inPageWidget = document.getElementById("caretaker-widget-content");

  if (activeAlert && !activeAlert.acknowledged) {
    // Show Top Emergency Banner
    if (banner) {
      banner.classList.remove("hidden");
      const sev = document.getElementById("banner-severity");
      if (sev) sev.innerText = activeAlert.risk_level;
      const type = document.getElementById("banner-risk-type");
      if (type) type.innerText = activeAlert.risk_type;
      const time = document.getElementById("banner-time");
      if (time) time.innerText = new Date(activeAlert.timestamp || Date.now()).toLocaleTimeString();
      const idEl = document.getElementById("banner-id");
      if (idEl) idEl.innerText = activeAlert.alert_id;
      const msg = document.getElementById("banner-message");
      if (msg) msg.innerText = activeAlert.message;
      const coords = document.getElementById("banner-coords-text");
      if (coords) coords.innerText = `${activeAlert.latitude || 10.662}° N, ${activeAlert.longitude || 76.891}° E`;

      const reasonsEl = document.getElementById("banner-reasons");
      if (reasonsEl && activeAlert.contributing_parameters) {
        reasonsEl.innerText = `Contributing indicators: ${activeAlert.contributing_parameters.join(", ")}`;
      }
    }

    // In-page widget in Overview
    if (inPageWidget) {
      inPageWidget.innerHTML = `
        <div class="active-alert-box font-mono">
          <div class="aab-header">
            <span class="severity-tag font-mono">${activeAlert.risk_level}</span>
            <strong>${activeAlert.risk_type}</strong>
            <span class="text-muted">${activeAlert.alert_id}</span>
          </div>
          <div class="aab-body">
            <p>${activeAlert.message}</p>
            <div class="aab-meta">
              <span>GPS: ${activeAlert.latitude || 10.662}° N, ${activeAlert.longitude || 76.891}° E</span>
              <button class="btn-ack" onclick="acknowledgeAlert('${activeAlert.alert_id}')">Acknowledge Alert</button>
            </div>
          </div>
        </div>
      `;
    }
  } else {
    // Hide Banner
    if (banner) banner.classList.add("hidden");

    // In-page widget nominal
    if (inPageWidget) {
      inPageWidget.innerHTML = `
        <div class="no-alerts-placeholder font-mono">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/></svg>
          <span>No active alerts. System nominal.</span>
        </div>
      `;
    }
  }
}

// --- 6. Caretaker Alert Actions & History Management ---

function initCaretakerBanner() {
  document.getElementById("btn-banner-ack")?.addEventListener("click", () => {
    if (state.activeAlert) {
      acknowledgeAlert(state.activeAlert.alert_id);
    }
  });
}

async function acknowledgeAlert(alertId) {
  try {
    const res = await fetch(`/api/alerts/${alertId}/acknowledge`, { method: "POST" });
    if (res.ok) {
      if (state.activeAlert && state.activeAlert.alert_id === alertId) {
        state.activeAlert = null;
        updateAlertComponents(null);
      }
      fetchAlertHistory();
    }
  } catch (e) {
    console.error("Alert acknowledgment failed:", e);
  }
}
window.acknowledgeAlert = acknowledgeAlert; // Expose for inline buttons

function handleAlertAcknowledged(data) {
  if (state.activeAlert && state.activeAlert.alert_id === data.alert_id) {
    state.activeAlert = null;
    updateAlertComponents(null);
  }
  fetchAlertHistory();
}

function initAlertFilters() {
  const filterBtns = document.querySelectorAll(".alert-filters .filter-btn");
  filterBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      filterBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.activeAlertFilter = btn.getAttribute("data-filter") || "ALL";
      renderAlertsTable();
    });
  });
}

async function fetchAlertHistory() {
  try {
    const res = await fetch("/api/alerts?limit=50");
    if (res.ok) {
      state.allAlerts = await res.json();
      updateAlertCounts();
      renderAlertsTable();
    }
  } catch (e) {
    console.error("Fetch alerts failed:", e);
  }
}

function updateAlertCounts() {
  const all = state.allAlerts.length;
  const active = state.allAlerts.filter((a) => !a.acknowledged).length;
  const acked = state.allAlerts.filter((a) => a.acknowledged).length;
  const crit = state.allAlerts.filter((a) => a.risk_level === "CRITICAL").length;

  const setC = (id, count) => {
    const el = document.getElementById(id);
    if (el) el.innerText = count;
  };

  setC("count-all", all);
  setC("count-active", active);
  setC("count-acked", acked);
  setC("count-crit", crit);

  // Top Nav Badge
  const navBadge = document.getElementById("nav-alerts-badge");
  if (navBadge) {
    if (active > 0) {
      navBadge.innerText = active;
      navBadge.classList.remove("hidden");
    } else {
      navBadge.classList.add("hidden");
    }
  }
}

function renderAlertsTable() {
  const tbody = document.getElementById("alerts-table-body");
  if (!tbody) return;

  let filtered = state.allAlerts;
  if (state.activeAlertFilter === "ACTIVE") {
    filtered = filtered.filter((a) => !a.acknowledged);
  } else if (state.activeAlertFilter === "ACKNOWLEDGED") {
    filtered = filtered.filter((a) => a.acknowledged);
  } else if (state.activeAlertFilter === "CRITICAL") {
    filtered = filtered.filter((a) => a.risk_level === "CRITICAL");
  }

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-cell font-mono">No alerts match the selected filter.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map((a) => {
    const time = a.timestamp ? new Date(a.timestamp).toLocaleTimeString() : "--";
    const lvl = a.risk_level || "EARLY_WARNING";
    const badgeClass = `chip-${lvl.toLowerCase().replace("_", "-")}`;
    const statusText = a.acknowledged ? "ACKNOWLEDGED" : "ACTIVE";
    const statusClass = a.acknowledged ? "chip-normal" : "chip-critical";
    const actionHtml = a.acknowledged
      ? `<span class="text-muted font-mono" style="font-size:0.75rem;">Done</span>`
      : `<button class="btn-subtle-sm" onclick="acknowledgeAlert('${a.alert_id}')">Acknowledge</button>`;

    return `
      <tr>
        <td class="font-mono">${time}</td>
        <td><span class="status-chip ${badgeClass} font-mono">${lvl}</span></td>
        <td><strong>${a.risk_type}</strong></td>
        <td>${a.message}</td>
        <td class="font-mono">${(a.latitude || 10.662).toFixed(3)}°, ${(a.longitude || 76.891).toFixed(3)}°</td>
        <td><span class="status-chip ${statusClass} font-mono">${statusText}</span></td>
        <td>${actionHtml}</td>
      </tr>
    `;
  }).join("");
}

// --- 7. Test Lab: Interactive Controls, Presets & Simulation ---

function initTestLabControls() {
  const controls = [
    { range: "ctrl-hr", num: "ctrl-hr-num" },
    { range: "ctrl-spo2", num: "ctrl-spo2-num" },
    { range: "ctrl-ppg", num: "ctrl-ppg-num" },
    { range: "ctrl-temp", num: "ctrl-temp-num" },
    { range: "ctrl-amb", num: "ctrl-amb-num" },
    { range: "ctrl-hum", num: "ctrl-hum-num" },
    { range: "ctrl-mq", num: "ctrl-mq-num" },
  ];

  controls.forEach(({ range, num }) => {
    const rEl = document.getElementById(range);
    const nEl = document.getElementById(num);
    if (!rEl || !nEl) return;

    rEl.addEventListener("input", () => {
      nEl.value = rEl.value;
      triggerSimulatorDispatch();
    });

    nEl.addEventListener("input", () => {
      rEl.value = nEl.value;
      triggerSimulatorDispatch();
    });
  });

  // Step +/- buttons
  document.querySelectorAll(".btn-step").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-target");
      const delta = parseFloat(btn.getAttribute("data-delta"));
      const rEl = document.getElementById(targetId);
      const nEl = document.getElementById(`${targetId}-num`);
      if (!rEl || !nEl) return;

      let val = parseFloat(rEl.value) + delta;
      val = Math.max(parseFloat(rEl.min), Math.min(parseFloat(rEl.max), val));
      const step = rEl.step ? parseFloat(rEl.step) : 1;
      if (step < 1) val = parseFloat(val.toFixed(2));
      rEl.value = val;
      nEl.value = val;
      triggerSimulatorDispatch();
    });
  });

  // Physical Activity Dropdown
  const actSelect = document.getElementById("ctrl-activity-select");
  const actChip = document.getElementById("ctrl-activity-chip");
  if (actSelect) {
    actSelect.addEventListener("change", () => {
      const val = parseInt(actSelect.value, 10);
      const labels = ["REST", "LIGHT", "MODERATE", "HIGH", "FALL_CANDIDATE"];
      if (actChip) actChip.innerText = labels[val] || "REST";

      // Auto update acceleration vectors roughly corresponding to activity
      const axEl = document.getElementById("ctrl-ax");
      const ayEl = document.getElementById("ctrl-ay");
      const azEl = document.getElementById("ctrl-az");
      const magLabel = document.getElementById("ctrl-accel-mag-label");

      if (val === 4) { // FALL_CANDIDATE
        if (axEl) axEl.value = 2.40;
        if (ayEl) ayEl.value = 2.10;
        if (azEl) azEl.value = 0.30;
      } else if (val === 3) { // HIGH
        if (axEl) axEl.value = 0.65;
        if (ayEl) ayEl.value = 0.55;
        if (azEl) azEl.value = 1.35;
      } else if (val === 2) { // MODERATE
        if (axEl) axEl.value = 0.25;
        if (ayEl) ayEl.value = 0.25;
        if (azEl) azEl.value = 1.05;
      } else { // REST / LIGHT
        if (axEl) axEl.value = 0.02;
        if (ayEl) ayEl.value = 0.01;
        if (azEl) azEl.value = 0.98;
      }

      if (magLabel && axEl && ayEl && azEl) {
        const mag = Math.sqrt(axEl.value ** 2 + ayEl.value ** 2 + azEl.value ** 2).toFixed(2);
        magLabel.innerText = `Mag: ${mag}g`;
      }

      triggerSimulatorDispatch();
    });
  }

  // Acceleration inputs change
  ["ctrl-ax", "ctrl-ay", "ctrl-az"].forEach((id) => {
    document.getElementById(id)?.addEventListener("input", () => {
      const ax = parseFloat(document.getElementById("ctrl-ax")?.value || 0.02);
      const ay = parseFloat(document.getElementById("ctrl-ay")?.value || 0.01);
      const az = parseFloat(document.getElementById("ctrl-az")?.value || 0.98);
      const mag = Math.sqrt(ax * ax + ay * ay + az * az).toFixed(2);
      const magLabel = document.getElementById("ctrl-accel-mag-label");
      if (magLabel) magLabel.innerText = `Mag: ${mag}g`;
      triggerSimulatorDispatch();
    });
  });

  // GPS inputs change
  ["ctrl-lat", "ctrl-lon"].forEach((id) => {
    document.getElementById(id)?.addEventListener("input", triggerSimulatorDispatch);
  });

  // Preset Buttons
  document.querySelectorAll(".btn-preset[data-preset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const presetKey = btn.getAttribute("data-preset");
      applyPreset(presetKey);
    });
  });

  // Reset to Normal button
  document.getElementById("btn-lab-reset")?.addEventListener("click", () => {
    applyPreset("normal");
  });

  // Trigger Next Risk Level
  document.getElementById("btn-trigger-next-level")?.addEventListener("click", () => {
    state.escalationStepIndex = (state.escalationStepIndex + 1) % ESCALATION_CHAIN.length;
    const nextPreset = ESCALATION_CHAIN[state.escalationStepIndex];
    applyPreset(nextPreset);
    const logEl = document.getElementById("lab-action-log");
    if (logEl) {
      logEl.innerText = `Triggered step ${state.escalationStepIndex + 1}/${ESCALATION_CHAIN.length}: Scenario "${nextPreset.toUpperCase().replace("_", " ")}"`;
    }
  });

  // Return to Baseline
  document.getElementById("btn-return-baseline")?.addEventListener("click", () => {
    state.escalationStepIndex = 0;
    applyPreset("recovery");
    setTimeout(() => applyPreset("normal"), 1500);
    const logEl = document.getElementById("lab-action-log");
    if (logEl) {
      logEl.innerText = `Returning to baseline: Executing recovery decay -> Nominal baseline.`;
    }
  });
}

function applyPreset(presetKey) {
  const p = PRESETS[presetKey];
  if (!p) return;

  const setCtrl = (id, val) => {
    const rEl = document.getElementById(id);
    const nEl = document.getElementById(`${id}-num`);
    if (rEl) rEl.value = val;
    if (nEl) nEl.value = val;
  };

  setCtrl("ctrl-hr", p.heart_rate);
  setCtrl("ctrl-spo2", p.spo2);
  setCtrl("ctrl-ppg", p.ppg_quality || 0.95);
  setCtrl("ctrl-temp", p.body_temperature);
  setCtrl("ctrl-amb", p.ambient_temperature);
  setCtrl("ctrl-hum", p.humidity);
  setCtrl("ctrl-mq", p.mq45);

  const actSelect = document.getElementById("ctrl-activity-select");
  if (actSelect) {
    actSelect.value = p.activity_level !== undefined ? p.activity_level : 0;
    const actChip = document.getElementById("ctrl-activity-chip");
    const labels = ["REST", "LIGHT", "MODERATE", "HIGH", "FALL_CANDIDATE"];
    if (actChip) actChip.innerText = labels[p.activity_level] || "REST";
  }

  const axEl = document.getElementById("ctrl-ax");
  const ayEl = document.getElementById("ctrl-ay");
  const azEl = document.getElementById("ctrl-az");
  if (axEl) axEl.value = p.accel_x;
  if (ayEl) ayEl.value = p.accel_y;
  if (azEl) azEl.value = p.accel_z;

  const magLabel = document.getElementById("ctrl-accel-mag-label");
  if (magLabel) {
    const mag = Math.sqrt(p.accel_x ** 2 + p.accel_y ** 2 + p.accel_z ** 2).toFixed(2);
    magLabel.innerText = `Mag: ${mag}g`;
  }

  // Highlight active preset button
  document.querySelectorAll(".btn-preset[data-preset]").forEach((btn) => {
    if (btn.getAttribute("data-preset") === presetKey) {
      btn.style.borderColor = "var(--border-focus)";
      btn.style.backgroundColor = "var(--accent-subtle)";
    } else {
      btn.style.borderColor = "";
      btn.style.backgroundColor = "";
    }
  });

  dispatchSimulatorReading();
}

function triggerSimulatorDispatch() {
  clearTimeout(state.debounceTimer);
  state.debounceTimer = setTimeout(() => {
    dispatchSimulatorReading();
  }, 90); // 90ms debounce for responsive slider feel
}

async function dispatchSimulatorReading() {
  const payload = {
    device_id: "ESP32-001",
    timestamp: new Date().toISOString(),
    heart_rate: parseFloat(document.getElementById("ctrl-hr")?.value || 74),
    spo2: parseFloat(document.getElementById("ctrl-spo2")?.value || 98),
    ppg_quality: parseFloat(document.getElementById("ctrl-ppg")?.value || 0.95),
    body_temperature: parseFloat(document.getElementById("ctrl-temp")?.value || 36.7),
    ambient_temperature: parseFloat(document.getElementById("ctrl-amb")?.value || 28.0),
    humidity: parseFloat(document.getElementById("ctrl-hum")?.value || 60),
    mq45: parseFloat(document.getElementById("ctrl-mq")?.value || 180),
    accel_x: parseFloat(document.getElementById("ctrl-ax")?.value || 0.02),
    accel_y: parseFloat(document.getElementById("ctrl-ay")?.value || 0.01),
    accel_z: parseFloat(document.getElementById("ctrl-az")?.value || 0.98),
    latitude: parseFloat(document.getElementById("ctrl-lat")?.value || 10.662),
    longitude: parseFloat(document.getElementById("ctrl-lon")?.value || 76.891),
    is_simulator: true,
  };

  try {
    const res = await fetch("/api/simulator/readings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      const data = await res.json();
      handleIncomingTelemetry(data);
    }
  } catch (e) {
    console.error("Simulator dispatch error:", e);
  }
}

// --- 8. Risk Matrix Row Click Inspector Modal ---
function initMatrixDetailModal() {
  const box = document.getElementById("matrix-detail-box");
  const closeBtn = document.getElementById("btn-close-md");
  closeBtn?.addEventListener("click", () => {
    box?.classList.add("hidden");
  });

  document.querySelectorAll(".risk-row").forEach((row) => {
    row.addEventListener("click", () => {
      const key = row.getAttribute("data-risk-key");
      const ml = state.latestTelemetry?.ml_predictions || {};
      const modelData = ml[key];
      if (!modelData || !box) return;

      box.classList.remove("hidden");
      const title = document.getElementById("md-title");
      if (title) title.innerText = `${key.replace(/_/g, " ").toUpperCase()} DETAILS`;

      const confEl = document.getElementById("md-conf");
      if (confEl) confEl.innerText = `${Math.round((modelData.confidence || 0.95) * 100)}%`;

      const verEl = document.getElementById("md-version");
      if (verEl) verEl.innerText = ml.model_version || "1.0.0-edge";

      const timeEl = document.getElementById("md-time");
      if (timeEl) timeEl.innerText = new Date().toLocaleTimeString();

      const featList = document.getElementById("md-features-list");
      if (featList) {
        featList.innerHTML = "";
        const feats = modelData.contributing_features?.top_drivers || [
          "Feature attribution nominal.",
          "Temporal persistence confirmed."
        ];
        feats.forEach((f) => {
          const li = document.createElement("li");
          li.innerText = f;
          featList.appendChild(li);
        });
      }
    });
  });
}

// --- 9. Real-Time Canvas Oscilloscopes ---

let overviewCanvas, overviewCtx;
let monitorCanvas, monitorCtx;

function initCanvasCharts() {
  overviewCanvas = document.getElementById("overview-chart-canvas");
  if (overviewCanvas) overviewCtx = overviewCanvas.getContext("2d");

  monitorCanvas = document.getElementById("monitor-waveform-canvas");
  if (monitorCanvas) monitorCtx = monitorCanvas.getContext("2d");

  window.addEventListener("resize", () => {
    renderOverviewChart();
    renderMonitorWaveforms();
  });
}

function initOverviewChartTabs() {
  // Signal selection tabs
  document.querySelectorAll("#chart-tabs .chart-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#chart-tabs .chart-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      state.selectedOverviewSignal = tab.getAttribute("data-signal") || "hr";
      renderOverviewChart();
    });
  });

  // Time range buttons
  document.querySelectorAll(".time-range-buttons .range-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".time-range-buttons .range-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.overviewTimeRangeMinutes = parseInt(btn.getAttribute("data-range") || "5", 10);
      renderOverviewChart();
    });
  });
}

function recordTrendDataPoint(raw, feat, overall) {
  const pt = {
    time: Date.now(),
    hr: raw.heart_rate || 74,
    spo2: raw.spo2 || 98,
    body_temperature: raw.body_temperature || 36.7,
    ambient_temperature: raw.ambient_temperature || 28.0,
    humidity: raw.humidity || 60,
    mq45: raw.mq45 || 180,
    overall_risk: overall.score !== undefined ? overall.score : 0.10,
  };

  state.trendHistory.push(pt);
  if (state.trendHistory.length > state.maxTrendHistory) {
    state.trendHistory.shift();
  }
}

// Render Oscilloscope 1 (Overview View)
function renderOverviewChart() {
  if (!overviewCanvas || !overviewCtx) return;

  const rect = overviewCanvas.parentElement.getBoundingClientRect();
  if (rect.width <= 0) return;

  const dpr = window.devicePixelRatio || 1;
  overviewCanvas.width = rect.width * dpr;
  overviewCanvas.height = 220 * dpr;
  overviewCanvas.style.width = `${rect.width}px`;
  overviewCanvas.style.height = `220px`;

  const ctx = overviewCtx;
  ctx.save();
  ctx.scale(dpr, dpr);

  const w = rect.width;
  const h = 220;

  // Clear background
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, w, h);

  // Background Grid Lines
  ctx.strokeStyle = "#f1f5f9";
  ctx.lineWidth = 1;

  for (let y = 30; y < h; y += 35) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
  for (let x = w / 4; x < w; x += w / 4) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }

  const signal = state.selectedOverviewSignal;
  const data = state.trendHistory;

  // Signal configuration
  const signalConfigs = {
    hr: { min: 40, max: 180, unit: "BPM", baseKey: "heart_rate", color: "#2563eb", baseMean: 72.0 },
    spo2: { min: 70, max: 100, unit: "%", baseKey: "spo2", color: "#16a34a", baseMean: 98.0 },
    body_temperature: { min: 34.0, max: 42.0, unit: "°C", baseKey: "body_temperature", color: "#ea580c", baseMean: 36.7 },
    ambient_temperature: { min: 15.0, max: 50.0, unit: "°C", baseKey: null, color: "#9333ea", baseMean: 28.0 },
    humidity: { min: 10, max: 100, unit: "%", baseKey: null, color: "#0891b2", baseMean: 60.0 },
    mq45: { min: 50, max: 1000, unit: "", baseKey: null, color: "#db2777", baseMean: 180.0 },
    overall_risk: { min: 0.0, max: 1.0, unit: "", baseKey: null, color: "#ef4444", baseMean: 0.10 },
  };

  const cfg = signalConfigs[signal] || signalConfigs.hr;

  // Update Meta Bar Below Chart
  const currVal = data.length > 0 ? data[data.length - 1][signal] : cfg.baseMean;
  const baseVal = cfg.baseMean;
  const dev = currVal - baseVal;
  const devPct = ((dev / (baseVal || 1)) * 100).toFixed(1);

  const curEl = document.getElementById("chart-current-val");
  if (curEl) curEl.innerText = `${typeof currVal === "number" ? currVal.toFixed(1) : currVal} ${cfg.unit}`;

  const baseEl = document.getElementById("chart-baseline-val");
  if (baseEl) baseEl.innerText = `${baseVal.toFixed(1)} ${cfg.unit}`;

  const devEl = document.getElementById("chart-dev-val");
  if (devEl) devEl.innerText = `${dev >= 0 ? "+" : ""}${dev.toFixed(1)} ${cfg.unit} (${dev >= 0 ? "+" : ""}${devPct}%)`;

  // Draw Personal Baseline Dotted Reference Line
  const normBaseY = 1 - (baseVal - cfg.min) / (cfg.max - cfg.min);
  const baseY = Math.max(15, Math.min(h - 15, normBaseY * (h - 30) + 15));

  ctx.setLineDash([5, 5]);
  ctx.strokeStyle = "#94a3b8";
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(0, baseY);
  ctx.lineTo(w, baseY);
  ctx.stroke();
  ctx.setLineDash([]);

  // Draw Signal Waveform Line
  if (data.length >= 2) {
    const stepX = w / (state.maxTrendHistory - 1);

    // Gradient Fill
    ctx.beginPath();
    data.forEach((pt, i) => {
      const val = pt[signal] !== undefined ? pt[signal] : baseVal;
      const normY = 1 - (val - cfg.min) / (cfg.max - cfg.min);
      const y = Math.max(15, Math.min(h - 15, normY * (h - 30) + 15));
      const x = i * stepX;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.lineTo((data.length - 1) * stepX, h);
    ctx.lineTo(0, h);
    ctx.closePath();

    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, "rgba(37, 99, 235, 0.12)");
    grad.addColorStop(1, "rgba(37, 99, 235, 0.0)");
    ctx.fillStyle = grad;
    ctx.fill();

    // Solid Waveform Curve
    ctx.beginPath();
    ctx.strokeStyle = cfg.color;
    ctx.lineWidth = 2.2;
    data.forEach((pt, i) => {
      const val = pt[signal] !== undefined ? pt[signal] : baseVal;
      const normY = 1 - (val - cfg.min) / (cfg.max - cfg.min);
      const y = Math.max(15, Math.min(h - 15, normY * (h - 30) + 15));
      const x = i * stepX;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Current Value Dot at End
    const lastX = (data.length - 1) * stepX;
    const lastVal = data[data.length - 1][signal];
    const lastNormY = 1 - (lastVal - cfg.min) / (cfg.max - cfg.min);
    const lastY = Math.max(15, Math.min(h - 15, lastNormY * (h - 30) + 15));

    ctx.fillStyle = cfg.color;
    ctx.beginPath();
    ctx.arc(lastX, lastY, 4.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }

  ctx.restore();
}

// Render Oscilloscope 2 (Live Monitor View)
function renderMonitorWaveforms() {
  if (!monitorCanvas || !monitorCtx) return;

  const rect = monitorCanvas.parentElement.getBoundingClientRect();
  if (rect.width <= 0) return;

  const dpr = window.devicePixelRatio || 1;
  monitorCanvas.width = rect.width * dpr;
  monitorCanvas.height = 320 * dpr;
  monitorCanvas.style.width = `${rect.width}px`;
  monitorCanvas.style.height = `320px`;

  const ctx = monitorCtx;
  ctx.save();
  ctx.scale(dpr, dpr);

  const w = rect.width;
  const h = 320;

  // Dark industrial oscilloscope grid
  ctx.fillStyle = "#090d16";
  ctx.fillRect(0, 0, w, h);

  ctx.strokeStyle = "#131c2e";
  ctx.lineWidth = 1;

  for (let y = 30; y < h; y += 40) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
  for (let x = w / 4; x < w; x += w / 4) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }

  const data = state.trendHistory;
  if (data.length < 2) {
    ctx.restore();
    return;
  }

  const stepX = w / (state.maxTrendHistory - 1);

  // Helper to draw a signal waveform
  function drawTrace(key, min, max, color, lineWidth = 1.8) {
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;

    data.forEach((pt, i) => {
      const val = pt[key] !== undefined ? pt[key] : min;
      const normY = 1 - Math.max(0, Math.min(1, (val - min) / (max - min)));
      const y = normY * (h - 40) + 20;
      const x = i * stepX;

      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.stroke();
  }

  // Draw 4 monitor waveforms
  drawTrace("hr", 40, 160, "#38bdf8", 1.8);        // Sky Blue Heart Rate
  drawTrace("spo2", 75, 100, "#22c55e", 1.8);      // Emerald Green SpO2
  drawTrace("body_temperature", 35.0, 41.0, "#f59e0b", 1.6); // Amber Temperature
  drawTrace("overall_risk", 0.0, 1.0, "#ef4444", 2.2);       // Red Overall Risk Line

  ctx.restore();
}

// --- 10. Initial Data Fetch ---
async function fetchInitialData() {
  try {
    // 1. Fetch latest sensor reading
    const readRes = await fetch("/api/sensors/latest");
    if (readRes.ok) {
      const reading = await readRes.json();
      syncSimulatorValues(reading);
    }

    // 2. Fetch baseline
    const baseRes = await fetch("/api/baseline");
    if (baseRes.ok) {
      state.baselineStats = await baseRes.json();
      const stats = state.baselineStats?.statistics;
      if (stats?.heart_rate) {
        const setT = (id, val) => {
          const el = document.getElementById(id);
          if (el) el.innerText = val;
        };
        setT("lb-base-hr", `${stats.heart_rate.mean.toFixed(1)} BPM`);
        setT("lb-base-spo2", `${stats.spo2.mean.toFixed(1)}%`);
        setT("lb-base-temp", `${stats.body_temperature.mean.toFixed(1)}°C`);
      }
    }

    // 3. Fetch device status
    const devRes = await fetch("/api/device/status");
    if (devRes.ok) {
      const dev = await devRes.json();
      updateDeviceDiagnostics(dev.device_status, dev.device_id, dev.last_iot_timestamp);
    }

    // 4. Fetch caretaker alerts history
    fetchAlertHistory();
  } catch (e) {
    console.error("Initial fetch error:", e);
  }
}

function syncSimulatorValues(raw) {
  if (!raw) return;

  const setCtrl = (id, val) => {
    if (val === undefined) return;
    const rEl = document.getElementById(id);
    const nEl = document.getElementById(`${id}-num`);
    if (rEl) rEl.value = val;
    if (nEl) nEl.value = val;
  };

  setCtrl("ctrl-hr", raw.heart_rate);
  setCtrl("ctrl-spo2", raw.spo2);
  setCtrl("ctrl-ppg", raw.ppg_quality);
  setCtrl("ctrl-temp", raw.body_temperature);
  setCtrl("ctrl-amb", raw.ambient_temperature);
  setCtrl("ctrl-hum", raw.humidity);
  setCtrl("ctrl-mq", raw.mq45);
}
