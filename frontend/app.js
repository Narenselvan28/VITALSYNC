/**
 * =============================================================================
 * AAROGYA-SHIELD: Front-End Application Controller
 * Handles WebSocket telemetry stream, REST API simulator dispatches,
 * real-time Canvas trend chart rendering (7 physiological & environmental signals),
 * dedicated 6-stage pipeline inspection, scenario injection, and caretaker alerts.
 * =============================================================================
 */

// Application State
const state = {
  mode: "IOT", // "IOT" or "SIMULATOR"
  activeTab: "dashboard", // "dashboard" or "pipeline"
  connected: false,
  ws: null,
  activeAlert: null,
  latestTelemetry: null,
  trendHistory: [],
  maxTrendHistory: 45,
  debounceTimer: null,
  baselineStats: null,
  activeSeries: {
    hr: true,
    spo2: true,
    temp: true,
    amb_temp: true,
    humidity: true,
    mq45: true,
    risk: true,
  },
};

// Color Tokens (Grounded Human Clinical Palette)
const COLORS = {
  LOW: "#10b981",          // Emerald
  EARLY_WARNING: "#f59e0b",// Ochre Amber
  ELEVATED: "#f97316",     // Terracotta
  CRITICAL: "#ef4444",     // Crimson
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
    accel_x: 0.1,
    accel_y: 0.1,
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
    accel_x: 0.02,
    accel_y: 0.01,
    accel_z: 0.98,
  },
  critical_multiparameter: {
    heart_rate: 142,
    spo2: 85,
    ppg_quality: 0.75,
    body_temperature: 39.8,
    ambient_temperature: 44.0,
    humidity: 86,
    mq45: 860,
    accel_x: 2.4,
    accel_y: 2.1,
    accel_z: 0.3,
  },
};

// Initialize Application on Page Load
document.addEventListener("DOMContentLoaded", () => {
  initWebSocket();
  initTabs();
  initSimulatorControls();
  initModeSwitch();
  initCaretakerBanner();
  initTrendCanvas();
  fetchInitialData();
});

// --- 1. WebSocket Streaming Connection ---
function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/live`;
  
  updateConnectionStatus(false, "Connecting...");

  state.ws = new WebSocket(wsUrl);

  state.ws.onopen = () => {
    updateConnectionStatus(true, "ONLINE");
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
    updateConnectionStatus(false, "DISCONNECTED");
    setTimeout(initWebSocket, 2500); // Auto reconnect
  };

  state.ws.onerror = (err) => {
    console.warn("[WS] Socket error:", err);
  };
}

function updateConnectionStatus(online, text) {
  state.connected = online;
  const dot = document.getElementById("system-status-dot");
  const txt = document.getElementById("system-status-text");
  if (online) {
    dot.className = "pulse-dot online-dot";
    txt.innerText = "ONLINE";
  } else {
    dot.className = "pulse-dot";
    dot.style.backgroundColor = "#ff1744";
    dot.style.boxShadow = "none";
    txt.innerText = text;
  }
}

// --- 2. Tab Navigation Switcher ---
function initTabs() {
  const btnDash = document.getElementById("tab-btn-dashboard");
  const btnPipe = document.getElementById("tab-btn-pipeline");
  const viewDash = document.querySelector(".terminal-workspace");
  const viewPipe = document.getElementById("view-pipeline");

  function switchTab(tab) {
    state.activeTab = tab;
    if (tab === "dashboard") {
      btnDash?.classList.add("active");
      btnPipe?.classList.remove("active");
      viewDash?.classList.remove("hidden");
      viewPipe?.classList.add("hidden");
      if (window.location.pathname === "/test") {
        window.history.pushState({}, "", "/");
      }
    } else {
      btnPipe?.classList.add("active");
      btnDash?.classList.remove("active");
      viewDash?.classList.add("hidden");
      viewPipe?.classList.remove("hidden");
      if (window.location.pathname !== "/test") {
        window.history.pushState({}, "", "/test");
      }
    }
  }

  btnDash?.addEventListener("click", () => switchTab("dashboard"));
  btnPipe?.addEventListener("click", () => switchTab("pipeline"));

  // Check URL on initial load
  if (window.location.pathname === "/test") {
    switchTab("pipeline");
  }
}

// --- 3. Handle Live Telemetry Update ---
function handleIncomingTelemetry(payload) {
  if (payload.event_type === "ALERT_ACKNOWLEDGED") {
    handleAlertAcknowledged(payload);
    return;
  }

  if (payload.event_type !== "TELEMETRY_UPDATE") return;

  state.latestTelemetry = payload;
  const raw = payload.raw_sensors || {};
  const feat = payload.features || {};
  const ml = payload.ml_predictions || {};
  const esc = payload.escalation || {};
  const overall = ml.overall_health_risk || {};

  // 1. Update IoT status badge
  updateDeviceStatus(payload.device_status);

  // 2. Update Hero Overall Status
  updateHeroOverall(overall, esc);

  // 3. Update Physiological Cards
  updatePhysiologicalCards(raw, feat);

  // 4. Update Environment Cards
  updateEnvironmentalCards(raw, feat);

  // 5. Update Activity & Motion Cards
  updateActivityCard(raw, feat);

  // 6. Update Risk Matrix
  updateRiskMatrix(ml);

  // 7. Update Real-Time Sidebar Pipeline Inspector
  updatePipelineInspector(raw, feat, ml, esc, payload.active_alert);

  // 8. Update Dedicated Full-Width Pipeline Test Stage
  updatePipelineTestStage(raw, feat, ml, esc, payload.active_alert);

  // 9. Update Caretaker Banner & Table
  if (payload.active_alert && !payload.active_alert.acknowledged) {
    showAlertBanner(payload.active_alert);
  } else {
    hideAlertBanner();
  }

  // 10. Update Trend Canvas History (All 7 Signals)
  recordTrendPoint(raw, overall);
  renderTrendChart();

  // 11. If in IoT mode, sync simulator sliders to show live incoming hardware values
  if (state.mode === "IOT") {
    syncSimulatorSliders(raw);
  }

  // Update sync timestamp
  const ts = payload.timestamp ? new Date(payload.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
  const syncEl = document.getElementById("last-sync-time");
  if (syncEl) syncEl.innerText = `Sync: ${ts}`;
}

function updateDeviceStatus(deviceStatus) {
  const el = document.getElementById("iot-status-badge");
  if (!el) return;
  const status = deviceStatus || "OFFLINE / NO RECENT DATA";
  el.innerText = status;
  if (status === "ONLINE") {
    el.style.color = "var(--emerald)";
    el.style.borderColor = "rgba(16, 185, 129, 0.4)";
  } else {
    el.style.color = "var(--amber)";
    el.style.borderColor = "rgba(245, 158, 11, 0.4)";
  }
}

// --- 4. DOM Updaters ---

function updateHeroOverall(overall, esc) {
  const score = overall.score !== undefined ? overall.score : 0.08;
  const level = esc.escalated_level || overall.risk_level || "LOW";
  const confidence = overall.confidence || 0.94;

  const scoreEl = document.getElementById("overall-score-display");
  if (scoreEl) scoreEl.innerText = score.toFixed(2);
  const confEl = document.getElementById("overall-confidence");
  if (confEl) confEl.innerText = `Confidence: ${(confidence * 100).toFixed(0)}%`;

  // SVG Progress Track
  const pct = Math.min(100, Math.max(4, score * 100));
  const gaugeFill = document.getElementById("overall-gauge-fill");
  if (gaugeFill) {
    if (gaugeFill.tagName.toLowerCase() === "line") {
      gaugeFill.setAttribute("x2", `${pct}`);
    } else {
      gaugeFill.setAttribute("stroke-dasharray", `${pct}, 100`);
    }
    const color = COLORS[level] || COLORS.LOW;
    gaugeFill.style.stroke = color;
  }

  // Level Badge
  const badge = document.getElementById("overall-risk-badge");
  if (badge) {
    badge.innerText = level.replace("_", " ");
    badge.className = `hero-level-text level-${level.toLowerCase().replace("_", "-")}`;
  }

  // Escalation Summary
  const escSummary = document.getElementById("escalation-trend-summary");
  if (escSummary) {
    if (level === "LOW") {
      escSummary.innerText = "Stable baseline. Temporal persistence: Nominal.";
    } else {
      escSummary.innerText = `Escalated to ${level.replace("_", " ")} (Persistent abnormal window: ${esc.persistence_count || 1} samples, Deviating indicators: ${esc.deviating_parameter_count || 1})`;
    }
  }

  // Primary Contributing Reasons List
  const reasonsList = document.getElementById("hero-contributing-factors");
  if (reasonsList) {
    reasonsList.innerHTML = "";
    const reasons = (esc.reasons && esc.reasons.length > 0) ? esc.reasons : (overall.contributing_features?.top_drivers || ["All parameters within baseline norms."]);
    reasons.forEach((r) => {
      const li = document.createElement("li");
      li.innerText = r;
      reasonsList.appendChild(li);
    });
  }
}

function updatePhysiologicalCards(raw, feat) {
  // Heart Rate
  const hr = Math.round(raw.heart_rate || 75);
  const hrEl = document.getElementById("val-heart-rate");
  if (hrEl) hrEl.innerText = hr;
  const hrDev = feat.hr_deviation !== undefined ? (feat.hr_deviation * 100).toFixed(1) : "0.0";
  const hrBadge = document.getElementById("hr-dev-badge");
  if (hrBadge) {
    const hrArrow = hrDev > 1.5 ? "↑" : hrDev < -1.5 ? "↓" : "→";
    hrBadge.innerHTML = `<span class="trend-arrow">${hrArrow}</span> ${hrDev >= 0 ? "+" : ""}${hrDev}%`;
    hrBadge.className = `trend-indicator-pill font-mono ${Math.abs(hrDev) > 25 ? "dev-bad" : Math.abs(hrDev) > 12 ? "dev-warn" : ""}`;
  }
  
  if (feat.hr_z_score !== undefined) {
    const zEl = document.getElementById("hr-zscore-span");
    if (zEl) zEl.innerText = `Z: ${feat.hr_z_score.toFixed(1)}`;
  }
  if (feat.baseline_summary?.heart_rate) {
    const bHr = document.getElementById("base-hr-mean");
    if (bHr) bHr.innerText = feat.baseline_summary.heart_rate.baseline_mean.toFixed(1);
  }

  // SpO2
  const spo2 = Math.round(raw.spo2 || 98);
  const spo2El = document.getElementById("val-spo2");
  if (spo2El) spo2El.innerText = spo2;
  const spo2Dev = feat.spo2_deviation !== undefined ? (feat.spo2_deviation * 100).toFixed(1) : "0.0";
  const spo2Badge = document.getElementById("spo2-dev-badge");
  if (spo2Badge) {
    const spo2Arrow = spo2Dev < -1.5 ? "↓" : spo2Dev > 1.5 ? "↑" : "→";
    spo2Badge.innerHTML = `<span class="trend-arrow">${spo2Arrow}</span> ${spo2Dev >= 0 ? "+" : ""}${spo2Dev}%`;
    spo2Badge.className = `trend-indicator-pill font-mono ${spo2Dev < -6 ? "dev-bad" : spo2Dev < -3 ? "dev-warn" : ""}`;
  }
  const ppgEl = document.getElementById("val-ppg-quality");
  if (ppgEl) ppgEl.innerText = (raw.ppg_quality || 0.95).toFixed(2);
  if (feat.baseline_summary?.spo2) {
    const bSpo2 = document.getElementById("base-spo2-mean");
    if (bSpo2) bSpo2.innerText = feat.baseline_summary.spo2.baseline_mean.toFixed(1);
  }

  // Body Temperature
  const temp = (raw.body_temperature || 36.8).toFixed(1);
  const btEl = document.getElementById("val-body-temp");
  if (btEl) btEl.innerText = temp;
  const tempF = ((raw.body_temperature || 36.8) * 9 / 5 + 32).toFixed(1);
  const fEl = document.getElementById("temp-f-span");
  if (fEl) fEl.innerText = `${tempF}°F`;
  const tempDev = feat.temp_deviation !== undefined ? feat.temp_deviation.toFixed(1) : "0.0";
  const tempBadge = document.getElementById("temp-dev-badge");
  if (tempBadge) {
    const tempArrow = tempDev > 0.4 ? "↑" : tempDev < -0.4 ? "↓" : "→";
    tempBadge.innerHTML = `<span class="trend-arrow">${tempArrow}</span> ${tempDev >= 0 ? "+" : ""}${tempDev}°C`;
    tempBadge.className = `trend-indicator-pill font-mono ${tempDev > 1.5 ? "dev-bad" : tempDev > 0.7 ? "dev-warn" : ""}`;
  }
  if (feat.baseline_summary?.body_temperature) {
    const bTemp = document.getElementById("base-temp-mean");
    if (bTemp) bTemp.innerText = feat.baseline_summary.body_temperature.baseline_mean.toFixed(1);
  }
}

function updateEnvironmentalCards(raw, feat) {
  const ambTemp = (raw.ambient_temperature || 28.0).toFixed(1);
  const hum = Math.round(raw.humidity || 60);
  const atEl = document.getElementById("val-ambient-temp");
  if (atEl) atEl.innerText = ambTemp;
  const ahEl = document.getElementById("val-ambient-humidity");
  if (ahEl) ahEl.innerText = hum;
  
  const hi = feat.heat_index || ambTemp;
  const hiBadge = document.getElementById("heat-index-badge");
  if (hiBadge) hiBadge.innerText = `HI ${hi}°C`;

  // MQ-45
  const mq = Math.round(raw.mq45 || 180);
  const mqEl = document.getElementById("val-mq45");
  if (mqEl) mqEl.innerText = mq;
  const mqPill = document.getElementById("mq45-status-pill");
  const mqDesc = document.getElementById("mq45-exposure-desc");
  if (mqPill && mqDesc) {
    if (mq > 650) {
      mqPill.innerText = "CRITICAL";
      mqPill.style.color = COLORS.CRITICAL;
      mqDesc.innerText = "Severe Exposure";
    } else if (mq > 400) {
      mqPill.innerText = "ELEVATED";
      mqPill.style.color = COLORS.ELEVATED;
      mqDesc.innerText = "Elevated Exposure";
    } else if (mq > 250) {
      mqPill.innerText = "EARLY_WARNING";
      mqPill.style.color = COLORS.EARLY_WARNING;
      mqDesc.innerText = "Mild Elevation";
    } else {
      mqPill.innerText = "MQ-45";
      mqPill.style.color = COLORS.LOW;
      mqDesc.innerText = "Baseline Air";
    }
  }
}

function updateActivityCard(raw, feat) {
  const label = feat.activity_level || feat.activity_label || "REST";
  const badge = document.getElementById("val-activity-badge");
  if (badge) {
    badge.innerText = label.replace("_", "-");
    if (label === "REST") badge.className = "status-chip chip-rest font-mono";
    else if (label === "LIGHT") badge.className = "status-chip chip-light font-mono";
    else if (label === "MODERATE") badge.className = "status-chip chip-mod font-mono";
    else if (label === "HIGH") badge.className = "status-chip chip-high font-mono";
    else if (label === "FALL_CANDIDATE" || label === "FALL-CANDIDATE") badge.className = "status-chip chip-fall font-mono";
  }

  const ax = raw.accel_x !== undefined ? raw.accel_x.toFixed(2) : "+0.02";
  const ay = raw.accel_y !== undefined ? raw.accel_y.toFixed(2) : "+0.01";
  const az = raw.accel_z !== undefined ? raw.accel_z.toFixed(2) : "+0.98";
  const mag = (feat.acceleration_magnitude || feat.accel_mag || 0.98).toFixed(2);

  const magEl = document.getElementById("val-accel-mag");
  if (magEl) magEl.innerText = `${mag}g`;
}

function updateRiskMatrix(ml) {
  const models = [
    { key: "respiratory_risk", id: "cell-respiratory", meterId: "meter-respiratory" },
    { key: "oxygenation_anomaly", id: "cell-oxygenation", meterId: "meter-oxygenation" },
    { key: "heat_stress_risk", id: "cell-heat", meterId: "meter-heat" },
    { key: "fatigue_strain_risk", id: "cell-fatigue", meterId: "meter-fatigue" },
    { key: "environmental_exposure_risk", id: "cell-env", meterId: "meter-environment" },
    { key: "general_health_anomaly", id: "cell-general", meterId: null },
  ];

  models.forEach(({ key, id, meterId }) => {
    const data = ml[key];
    if (!data) return;

    const score = (data.score || 0.1).toFixed(2);
    const level = data.risk_level || "LOW";
    const conf = Math.round((data.confidence || 0.95) * 100);

    const scoreEl = document.getElementById(`${id}-score`);
    const badgeEl = document.getElementById(`${id}-badge`);
    const confEl = document.getElementById(`${id}-conf`);

    if (scoreEl) scoreEl.innerText = score;
    if (badgeEl) {
      badgeEl.innerText = level.replace("_", " ");
      badgeEl.style.color = COLORS[level] || COLORS.LOW;
      badgeEl.style.borderColor = COLORS[level] || COLORS.LOW;
    }
    if (confEl) confEl.innerText = `${conf}%`;

    // Quick sub-meter on hero card
    if (meterId) {
      const fillEl = document.getElementById(meterId);
      const valEl = document.getElementById(`${meterId}-val`);
      if (fillEl && valEl) {
        fillEl.style.width = `${Math.min(100, Math.max(10, data.score * 100))}%`;
        fillEl.style.backgroundColor = COLORS[level] || COLORS.LOW;
        valEl.innerText = level.replace("_", " ");
        valEl.style.color = COLORS[level] || COLORS.LOW;
      }
    }
  });
}

function updatePipelineInspector(raw, feat, ml, esc, alert) {
  // Step 1: Input
  const box1 = document.getElementById("pipe-input-box");
  if (box1) {
    box1.innerHTML = `
      <code class="font-mono">
        HR: ${Math.round(raw.heart_rate || 75)} BPM, SpO2: ${Math.round(raw.spo2 || 98)}% (PPG: ${(raw.ppg_quality || 0.95).toFixed(2)})<br>
        Core: ${(raw.body_temperature || 36.8).toFixed(1)}°C, Amb: ${(raw.ambient_temperature || 28.0).toFixed(1)}°C, Hum: ${Math.round(raw.humidity || 60)}%<br>
        MQ-45: ${Math.round(raw.mq45 || 180)}, Act: ${feat.activity_level || feat.activity_label || "REST"} (${(feat.acceleration_magnitude || 0.98).toFixed(2)}g)
      </code>
    `;
  }

  // Step 2: Features
  const sDev = feat.spo2_deviation !== undefined ? (feat.spo2_deviation * 100).toFixed(1) : "0.0";
  const hDev = feat.hr_deviation !== undefined ? (feat.hr_deviation * 100).toFixed(1) : "0.0";
  const tDev = feat.temp_deviation !== undefined ? feat.temp_deviation.toFixed(2) : "0.00";
  const box2 = document.getElementById("pipe-features-box");
  if (box2) {
    box2.innerHTML = `
      <code class="font-mono">
        SpO2 dev: ${sDev}% (Z: ${(feat.spo2_z_score || 0).toFixed(1)})<br>
        HR dev: ${hDev}% (Z: ${(feat.hr_z_score || 0).toFixed(1)})<br>
        Temp dev: +${tDev}°C, HI: ${feat.heat_index || 28}°C<br>
        Fall Detected: ${feat.is_fall_candidate ? "YES" : "NO"}
      </code>
    `;
  }

  // Step 3: ML Models
  const resp = ml.respiratory_risk ? ml.respiratory_risk.score.toFixed(2) : "0.08";
  const heat = ml.heat_stress_risk ? ml.heat_stress_risk.score.toFixed(2) : "0.10";
  const anom = ml.general_health_anomaly ? ml.general_health_anomaly.score.toFixed(2) : "0.12";
  const box3 = document.getElementById("pipe-models-box");
  if (box3) {
    box3.innerHTML = `
      <code class="font-mono">
        Resp Risk: ${resp} (${ml.respiratory_risk?.risk_level || "LOW"})<br>
        Heat Risk: ${heat} (${ml.heat_stress_risk?.risk_level || "LOW"})<br>
        Gen Anomaly: ${anom} (${ml.general_health_anomaly?.risk_level || "LOW"})<br>
        Version: ${ml.model_version || "1.0.0-edge"}
      </code>
    `;
  }

  // Step 4: Escalation
  const escLevel = esc.escalated_level || "LOW";
  const box4 = document.getElementById("pipe-escalation-box");
  if (box4) {
    box4.innerHTML = `
      <code class="font-mono">
        Escalated: <strong style="color:${COLORS[escLevel]}">${escLevel}</strong><br>
        Persistence: ${esc.persistence_count || 0}/5 samples<br>
        Deviating Indicators: ${esc.deviating_parameter_count || 0}
      </code>
    `;
  }

  // Step 5: Alert
  const alertEl = document.getElementById("pipe-alert-box");
  if (alertEl) {
    if (alert && !alert.acknowledged) {
      alertEl.innerHTML = `
        <code class="font-mono">
          ID: ${alert.alert_id}<br>
          Level: <strong style="color:${COLORS[alert.risk_level]}">${alert.risk_level}</strong><br>
          Type: ${alert.risk_type}<br>
          Status: Caretaker Notified
        </code>
      `;
    } else {
      alertEl.innerHTML = `
        <code class="font-mono">
          Status: Normal / Standby<br>
          No critical alerts active
        </code>
      `;
    }
  }
}

function updatePipelineTestStage(raw, feat, ml, esc, alert) {
  const setEl = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.innerText = text;
  };

  const hr = Math.round(raw.heart_rate || 75);
  const spo2 = Math.round(raw.spo2 || 98);
  const ppg = (raw.ppg_quality || 0.95).toFixed(2);
  const bt = (raw.body_temperature || 36.8).toFixed(1);
  const at = (raw.ambient_temperature || 28.0).toFixed(1);
  const hum = Math.round(raw.humidity || 60);
  const mq = Math.round(raw.mq45 || 180);
  const ax = (raw.accel_x || 0.02).toFixed(2);
  const ay = (raw.accel_y || 0.01).toFixed(2);
  const az = (raw.accel_z || 0.98).toFixed(2);
  const lat = (raw.latitude || 10.662).toFixed(3);
  const lon = (raw.longitude || 76.891).toFixed(3);

  // Stage 1
  setEl("pvs-hr", `${hr} BPM`);
  setEl("pvs-spo2", `${spo2}%`);
  setEl("pvs-ppg", ppg);
  setEl("pvs-bt", `${bt}°C`);
  setEl("pvs-at", `${at}°C`);
  setEl("pvs-hum", `${hum}%`);
  setEl("pvs-mq", `${mq}`);
  setEl("pvs-accel", `X:${ax}, Y:${ay}, Z:${az}`);
  setEl("pvs-gps", `${lat}° N, ${lon}° E`);

  // Stage 2
  setEl("pvs-mag", `${(feat.acceleration_magnitude || feat.accel_mag || 0.98).toFixed(2)}g`);
  setEl("pvs-act", feat.activity_level || feat.activity_label || "REST");
  setEl("pvs-hi", `${(feat.heat_index || at)}°C`);
  setEl("pvs-hr-trend", `${(feat.hr_trend || feat.hr_roc || 0) >= 0 ? "+" : ""}${(feat.hr_trend || feat.hr_roc || 0).toFixed(2)} BPM/s`);
  setEl("pvs-spo2-trend", `${(feat.spo2_trend || feat.spo2_roc || 0) >= 0 ? "+" : ""}${(feat.spo2_trend || feat.spo2_roc || 0).toFixed(2)} %/s`);
  setEl("pvs-temp-trend", `${(feat.temperature_trend || feat.temp_roc || 0) >= 0 ? "+" : ""}${(feat.temperature_trend || feat.temp_roc || 0).toFixed(2)} °C/s`);
  setEl("pvs-sigq", `${(feat.signal_quality || feat.ppg_quality || 0.95).toFixed(2)}`);
  setEl("pvs-fall", (feat.is_fall_candidate || (feat.activity_level === "FALL_CANDIDATE")) ? "YES (DETECTED)" : "NO");

  // Stage 3
  const hrDev = feat.hr_deviation !== undefined ? (feat.hr_deviation * 100).toFixed(1) : "0.0";
  const spo2Dev = feat.spo2_deviation !== undefined ? (feat.spo2_deviation * 100).toFixed(1) : "0.0";
  const tempDev = feat.temp_deviation !== undefined ? feat.temp_deviation.toFixed(2) : "0.00";
  setEl("pvs-hr-dev", `${hrDev >= 0 ? "+" : ""}${hrDev}%`);
  setEl("pvs-hr-z", `${(feat.hr_z_score || 0).toFixed(2)}`);
  setEl("pvs-spo2-dev", `${spo2Dev >= 0 ? "+" : ""}${spo2Dev}%`);
  setEl("pvs-spo2-z", `${(feat.spo2_z_score || 0).toFixed(2)}`);
  setEl("pvs-temp-dev", `${tempDev >= 0 ? "+" : ""}${tempDev}°C`);
  setEl("pvs-temp-z", `${(feat.temp_z_score || 0).toFixed(2)}`);
  setEl("pvs-mq-z", `${(feat.mq45_z_score || 0).toFixed(2)}`);
  setEl("pvs-base-summary", feat.baseline_summary?.heart_rate ? `HR Mean: ${feat.baseline_summary.heart_rate.baseline_mean.toFixed(1)}, SpO2: ${feat.baseline_summary.spo2.baseline_mean.toFixed(1)}%` : "Active");

  // Stage 4
  const getMlStr = (m) => m ? `${m.score.toFixed(2)} (${m.risk_level})` : "0.10 (LOW)";
  setEl("pvs-ml-resp", getMlStr(ml.respiratory_risk));
  setEl("pvs-ml-oxy", getMlStr(ml.oxygenation_anomaly));
  setEl("pvs-ml-heat", getMlStr(ml.heat_stress_risk));
  setEl("pvs-ml-fatigue", getMlStr(ml.fatigue_strain_risk));
  setEl("pvs-ml-env", getMlStr(ml.environmental_exposure_risk));
  setEl("pvs-ml-gen", getMlStr(ml.general_health_anomaly));
  setEl("pvs-ml-overall", getMlStr(ml.overall_health_risk));
  setEl("pvs-ml-ver", ml.model_version || ml.overall_health_risk?.model_version || "1.0.0-edge");

  // Stage 5
  const escLevel = esc.escalated_level || "LOW";
  const escEl = document.getElementById("pvs-esc-level");
  if (escEl) {
    escEl.innerText = escLevel.replace("_", " ");
    escEl.style.color = COLORS[escLevel] || COLORS.LOW;
  }
  setEl("pvs-esc-persist", `${esc.persistence_count || 0} / 5 samples`);
  setEl("pvs-esc-devcount", `${esc.deviating_parameter_count || 0} parameters`);

  const reasonsList = document.getElementById("pvs-esc-reasons");
  if (reasonsList) {
    reasonsList.innerHTML = "";
    const reasons = esc.reasons && esc.reasons.length > 0 ? esc.reasons : ["All indicators tracking personal baseline."];
    reasons.forEach((r) => {
      const li = document.createElement("li");
      li.innerText = r;
      reasonsList.appendChild(li);
    });
  }

  // Stage 6
  if (alert && !alert.acknowledged) {
    setEl("pvs-alt-status", `ACTIVE ALERT (${alert.risk_level})`);
    const statEl = document.getElementById("pvs-alt-status");
    if (statEl) statEl.style.color = COLORS[alert.risk_level] || COLORS.CRITICAL;
    setEl("pvs-alt-id", alert.alert_id);
    setEl("pvs-alt-type", alert.risk_type);
    setEl("pvs-alt-msg", alert.message);
    setEl("pvs-alt-gps", `${alert.latitude || 10.662}° N, ${alert.longitude || 76.891}° E`);
    setEl("pvs-alt-ack", "PENDING ACKNOWLEDGMENT");
  } else {
    setEl("pvs-alt-status", "STANDBY (No Active Alert)");
    const statEl = document.getElementById("pvs-alt-status");
    if (statEl) statEl.style.color = COLORS.LOW;
    setEl("pvs-alt-id", "-");
    setEl("pvs-alt-type", "Nominal");
    setEl("pvs-alt-msg", "All primary indicators within normal thresholds.");
    setEl("pvs-alt-gps", `${lat}° N, ${lon}° E`);
    setEl("pvs-alt-ack", "None Required");
  }
}

// --- 5. Caretaker Alert Banner & Modal Logic ---

function initCaretakerBanner() {
  document.getElementById("btn-banner-ack")?.addEventListener("click", () => {
    if (state.activeAlert) {
      acknowledgeAlert(state.activeAlert.alert_id);
    }
  });

  document.getElementById("btn-refresh-alerts")?.addEventListener("click", () => {
    fetchAlertHistory();
  });
}

function showAlertBanner(alert) {
  state.activeAlert = alert;
  const banner = document.getElementById("caretaker-banner");
  if (!banner) return;
  banner.classList.remove("hidden");

  document.getElementById("banner-risk-level").innerText = alert.risk_level;
  document.getElementById("banner-risk-type").innerText = alert.risk_type;
  document.getElementById("banner-alert-id").innerText = alert.alert_id;
  document.getElementById("banner-alert-msg").innerText = alert.message;
  document.getElementById("banner-alert-location").innerText = `📍 Lat: ${alert.latitude || 10.662}, Lon: ${alert.longitude || 76.891}`;

  const chipsContainer = document.getElementById("banner-alert-reasons");
  if (chipsContainer) {
    chipsContainer.innerHTML = "";
    if (alert.contributing_parameters) {
      alert.contributing_parameters.forEach((param) => {
        const chip = document.createElement("span");
        chip.className = "reason-chip";
        chip.innerText = param;
        chipsContainer.appendChild(chip);
      });
    }
  }
}

function hideAlertBanner() {
  state.activeAlert = null;
  const banner = document.getElementById("caretaker-banner");
  if (banner) banner.classList.add("hidden");
}

async function acknowledgeAlert(alertId) {
  try {
    const res = await fetch(`/api/alerts/${alertId}/acknowledge`, { method: "POST" });
    if (res.ok) {
      hideAlertBanner();
      fetchAlertHistory();
    }
  } catch (e) {
    console.error("Ack error:", e);
  }
}

function handleAlertAcknowledged(data) {
  if (state.activeAlert && state.activeAlert.alert_id === data.alert_id) {
    hideAlertBanner();
  }
  fetchAlertHistory();
}

async function fetchAlertHistory() {
  try {
    const res = await fetch("/api/alerts?limit=25");
    if (res.ok) {
      const alerts = await res.json();
      renderAlertsTable(alerts);
    }
  } catch (e) {
    console.error("Fetch alerts error:", e);
  }
}

function renderAlertsTable(alerts) {
  const tbody = document.getElementById("alert-history-tbody");
  if (!tbody) return;
  if (!alerts || alerts.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-cell font-mono">No caretaker alerts recorded yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = alerts.map((a) => {
    const time = a.timestamp ? new Date(a.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "-";
    const levelColor = COLORS[a.risk_level] || "#fff";
    const statusBadge = a.acknowledged
      ? `<span class="table-ack-badge">Ack</span>`
      : `<span class="table-unack-badge">Active</span>`;
    const actionBtn = a.acknowledged
      ? `<small style="color:var(--text-tertiary)">Done</small>`
      : `<button class="btn-table-ack" onclick="acknowledgeAlert('${a.alert_id}')">Ack</button>`;

    return `
      <tr>
        <td><code>${a.alert_id}</code></td>
        <td>${time}</td>
        <td><strong style="color:${levelColor}">${a.risk_level}</strong></td>
        <td>${a.risk_type}</td>
        <td>${statusBadge}</td>
        <td>${actionBtn}</td>
      </tr>
    `;
  }).join("");
}

// --- 6. Simulator Controls & Preset Logic ---

function initSimulatorControls() {
  const controls = [
    { slider: "sim-hr", num: "sim-hr-num" },
    { slider: "sim-spo2", num: "sim-spo2-num" },
    { slider: "sim-ppg", num: "sim-ppg-num" },
    { slider: "sim-temp", num: "sim-temp-num" },
    { slider: "sim-amb-temp", num: "sim-amb-temp-num" },
    { slider: "sim-humidity", num: "sim-humidity-num" },
    { slider: "sim-mq45", num: "sim-mq45-num" },
    { slider: "sim-ax", num: "sim-ax-num" },
    { slider: "sim-ay", num: "sim-ay-num" },
    { slider: "sim-az", num: "sim-az-num" },
  ];

  controls.forEach(({ slider, num }) => {
    const sEl = document.getElementById(slider);
    const nEl = document.getElementById(num);
    if (!sEl || !nEl) return;

    sEl.addEventListener("input", () => {
      nEl.value = sEl.value;
      triggerSimulatorDispatch();
    });

    nEl.addEventListener("input", () => {
      sEl.value = nEl.value;
      triggerSimulatorDispatch();
    });
  });

  // Step +/- buttons
  document.querySelectorAll(".btn-step").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-target");
      const delta = parseFloat(btn.getAttribute("data-delta"));
      const sEl = document.getElementById(targetId);
      const nEl = document.getElementById(`${targetId}-num`);
      if (!sEl || !nEl) return;
      let val = parseFloat(sEl.value) + delta;
      val = Math.max(parseFloat(sEl.min), Math.min(parseFloat(sEl.max), val));
      const step = sEl.step ? parseFloat(sEl.step) : 1;
      if (step < 1) val = parseFloat(val.toFixed(2));
      sEl.value = val;
      nEl.value = val;
      triggerSimulatorDispatch();
    });
  });

  // Preset buttons (works in both sidebar and full-screen test view)
  document.querySelectorAll(".chip-btn[data-preset], .preset-chip-btn, .preset-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const presetName = btn.getAttribute("data-preset");
      applyPreset(presetName);
      // Highlight active preset
      document.querySelectorAll(".chip-btn[data-preset], .preset-chip-btn").forEach((b) => {
        if (b.getAttribute("data-preset") === presetName) b.classList.add("active-preset");
        else b.classList.remove("active-preset");
      });
    });
  });

  // Reset button
  document.getElementById("btn-reset-simulator")?.addEventListener("click", () => {
    applyPreset("normal");
  });

  // Recalibrate baseline button
  document.getElementById("btn-recalibrate-baseline")?.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/baseline/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_id: "ESP32-001" }),
      });
      if (res.ok) {
        const chip = document.getElementById("baseline-chip-text");
        if (chip) chip.innerText = "Personal Baseline: Recalibrating (0/30 Samples)...";
      }
    } catch (e) {
      console.error("Recalibrate error:", e);
    }
  });
}

function applyPreset(presetKey) {
  const p = PRESETS[presetKey];
  if (!p) return;

  // Automatically switch to Simulator Mode if not already
  setMode("SIMULATOR");

  const setField = (id, val) => {
    const sEl = document.getElementById(id);
    const nEl = document.getElementById(`${id}-num`);
    if (sEl) sEl.value = val;
    if (nEl) nEl.value = val;
  };

  setField("sim-hr", p.heart_rate);
  setField("sim-spo2", p.spo2);
  setField("sim-ppg", p.ppg_quality || 0.95);
  setField("sim-temp", p.body_temperature);
  setField("sim-amb-temp", p.ambient_temperature);
  setField("sim-humidity", p.humidity);
  setField("sim-mq45", p.mq45);
  setField("sim-ax", p.accel_x);
  setField("sim-ay", p.accel_y);
  setField("sim-az", p.accel_z);

  dispatchSimulatorReading();
}

function triggerSimulatorDispatch() {
  // Ensure mode is SIMULATOR when user interacts with dials
  setMode("SIMULATOR");

  clearTimeout(state.debounceTimer);
  state.debounceTimer = setTimeout(() => {
    dispatchSimulatorReading();
  }, 90); // 90ms debounce for smooth slider feel
}

async function dispatchSimulatorReading() {
  const payload = {
    device_id: "ESP32-001",
    timestamp: new Date().toISOString(),
    heart_rate: parseFloat(document.getElementById("sim-hr")?.value || 75),
    spo2: parseFloat(document.getElementById("sim-spo2")?.value || 98),
    ppg_quality: parseFloat(document.getElementById("sim-ppg")?.value || 0.95),
    body_temperature: parseFloat(document.getElementById("sim-temp")?.value || 36.8),
    ambient_temperature: parseFloat(document.getElementById("sim-amb-temp")?.value || 28.0),
    humidity: parseFloat(document.getElementById("sim-humidity")?.value || 60),
    accel_x: parseFloat(document.getElementById("sim-ax")?.value || 0.02),
    accel_y: parseFloat(document.getElementById("sim-ay")?.value || 0.01),
    accel_z: parseFloat(document.getElementById("sim-az")?.value || 0.98),
    mq45: parseFloat(document.getElementById("sim-mq45")?.value || 180),
    latitude: parseFloat(document.getElementById("sim-lat")?.value || 10.662),
    longitude: parseFloat(document.getElementById("sim-lon")?.value || 76.891),
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
      // Update locally in case WS has slight lag
      handleIncomingTelemetry(data);
    }
  } catch (e) {
    console.error("Simulator dispatch error:", e);
  }
}

function syncSimulatorSliders(raw) {
  const setField = (id, val) => {
    if (val === undefined) return;
    const sEl = document.getElementById(id);
    const nEl = document.getElementById(`${id}-num`);
    if (sEl) sEl.value = val;
    if (nEl) nEl.value = val;
  };

  setField("sim-hr", raw.heart_rate);
  setField("sim-spo2", raw.spo2);
  setField("sim-ppg", raw.ppg_quality);
  setField("sim-temp", raw.body_temperature);
  setField("sim-amb-temp", raw.ambient_temperature);
  setField("sim-humidity", raw.humidity);
  setField("sim-mq45", raw.mq45);
  setField("sim-ax", raw.accel_x);
  setField("sim-ay", raw.accel_y);
  setField("sim-az", raw.accel_z);
}

// --- 7. Mode Switch Logic ---

function initModeSwitch() {
  document.getElementById("btn-iot-mode")?.addEventListener("click", () => setMode("IOT"));
  document.getElementById("btn-simulator-mode")?.addEventListener("click", () => setMode("SIMULATOR"));
}

function setMode(mode) {
  state.mode = mode;
  const btnIot = document.getElementById("btn-iot-mode");
  const btnSim = document.getElementById("btn-simulator-mode");

  if (mode === "IOT") {
    btnIot?.classList.add("active");
    btnSim?.classList.remove("active");
  } else {
    btnSim?.classList.add("active");
    btnIot?.classList.remove("active");
  }
}

// --- 8. Real-Time Canvas Trend Chart (7 Required Signals) ---

let canvas, ctx;

function initTrendCanvas() {
  canvas = document.getElementById("live-telemetry-canvas");
  if (!canvas) return;
  ctx = canvas.getContext("2d");
  resizeCanvas();
  window.addEventListener("resize", resizeCanvas);

  // Click legend items to toggle series
  document.querySelectorAll(".oscilloscope-legend .legend-item").forEach((item) => {
    item.addEventListener("click", () => {
      const seriesKey = item.getAttribute("data-series");
      if (!seriesKey) return;
      state.activeSeries[seriesKey] = !state.activeSeries[seriesKey];
      if (state.activeSeries[seriesKey]) {
        item.classList.add("mark-active");
      } else {
        item.classList.remove("mark-active");
      }
      renderTrendChart();
    });
  });
}

function resizeCanvas() {
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * window.devicePixelRatio;
  canvas.height = rect.height * window.devicePixelRatio;
  ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
  renderTrendChart();
}

function recordTrendPoint(raw, overall) {
  state.trendHistory.push({
    hr: raw.heart_rate || 75,
    spo2: raw.spo2 || 98,
    temp: raw.body_temperature || 36.8,
    amb_temp: raw.ambient_temperature || 28.0,
    humidity: raw.humidity || 60,
    mq45: raw.mq45 || 180,
    risk: overall.score || 0.1,
  });

  if (state.trendHistory.length > state.maxTrendHistory) {
    state.trendHistory.shift();
  }
}

function renderTrendChart() {
  if (!ctx || !canvas) return;

  const width = canvas.width / window.devicePixelRatio;
  const height = canvas.height / window.devicePixelRatio;

  ctx.clearRect(0, 0, width, height);

  // 1. Subtle Dotted Oscilloscope Grid Overlay
  ctx.save();
  ctx.strokeStyle = "rgba(255, 255, 255, 0.045)";
  ctx.lineWidth = 1;
  ctx.setLineDash([2, 4]);

  // Horizontal guide lines
  [0.25, 0.5, 0.75].forEach((ratio) => {
    const y = Math.round(height * ratio);
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  });

  // Vertical time tick lines
  [0.25, 0.5, 0.75].forEach((ratio) => {
    const x = Math.round(width * ratio);
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  });
  ctx.restore();

  const data = state.trendHistory;
  if (data.length < 2) return;

  const stepX = width / (state.maxTrendHistory - 1);

  // 2. Risk Score Gradient Fill Underneath
  if (state.activeSeries.risk) {
    ctx.save();
    const riskGrad = ctx.createLinearGradient(0, 0, 0, height);
    riskGrad.addColorStop(0, "rgba(20, 184, 166, 0.22)");
    riskGrad.addColorStop(0.7, "rgba(20, 184, 166, 0.05)");
    riskGrad.addColorStop(1, "rgba(20, 184, 166, 0.0)");

    ctx.fillStyle = riskGrad;
    ctx.beginPath();
    data.forEach((pt, i) => {
      const normY = pt.risk;
      const y = height - (normY * (height - 30) + 15);
      const x = i * stepX;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.lineTo((data.length - 1) * stepX, height);
    ctx.lineTo(0, height);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  // 3. Helper curve drawer for crisp series lines
  function drawSeries(key, minVal, maxVal, strokeColor, lineWidth = 1.6) {
    if (!state.activeSeries[key]) return;
    ctx.save();
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = lineWidth;
    ctx.beginPath();

    data.forEach((pt, i) => {
      const val = pt[key];
      const normY = Math.max(0, Math.min(1, (val - minVal) / (maxVal - minVal)));
      const y = height - (normY * (height - 30) + 15);
      const x = i * stepX;

      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.stroke();
    ctx.restore();
  }

  // Draw all 7 required series
  drawSeries("hr", 40, 160, "#38bdf8", 1.8);        // Sky Blue
  drawSeries("spo2", 80, 100, "#10b981", 1.8);      // Emerald Green
  drawSeries("temp", 35.0, 41.0, "#f59e0b", 1.8);    // Ochre Amber
  drawSeries("amb_temp", 15.0, 50.0, "#c084fc", 1.4);// Purple
  drawSeries("humidity", 20.0, 100.0, "#06b6d4", 1.4);// Cyan
  drawSeries("mq45", 50.0, 950.0, "#f472b6", 1.4);   // Pink
  drawSeries("risk", 0.0, 1.0, "#14b8a6", 2.0);      // Soft Teal Risk Envelope
}

// --- 9. Fetch Initial Data on Startup ---
async function fetchInitialData() {
  try {
    // 1. Fetch latest reading
    const readRes = await fetch("/api/sensors/latest");
    if (readRes.ok) {
      const raw = await readRes.json();
      syncSimulatorSliders(raw);
    }

    // 2. Fetch baseline
    const baseRes = await fetch("/api/baseline");
    if (baseRes.ok) {
      state.baselineStats = await baseRes.json();
      if (state.baselineStats.statistics?.heart_rate) {
        const bHr = document.getElementById("base-hr-mean");
        if (bHr) bHr.innerText = state.baselineStats.statistics.heart_rate.mean.toFixed(1);
        const bSpo2 = document.getElementById("base-spo2-mean");
        if (bSpo2) bSpo2.innerText = state.baselineStats.statistics.spo2.mean.toFixed(1);
        const bTemp = document.getElementById("base-temp-mean");
        if (bTemp) bTemp.innerText = state.baselineStats.statistics.body_temperature.mean.toFixed(1);
      }
    }

    // 3. Fetch device status
    const devRes = await fetch("/api/device/status");
    if (devRes.ok) {
      const devData = await devRes.json();
      updateDeviceStatus(devData.device_status);
    }

    // 4. Fetch alert history
    fetchAlertHistory();
  } catch (e) {
    console.error("Initial fetch error:", e);
  }
}
