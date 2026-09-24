# VITALSYNC: Edge-AI Personal Health Monitoring & Early-Warning System

[![System Status](https://img.shields.io/badge/System-ONLINE-00e676.svg)](#)
[![Hardware Target](https://img.shields.io/badge/Edge%20Target-Raspberry%20Pi%204-00f0ff.svg)](#)
[![Sensor Node](https://img.shields.io/badge/Sensor%20Node-ESP32%20DevKit-ffb300.svg)](#)
[![Clinical Dataset](https://img.shields.io/badge/Dataset-PhysioNet%20BIDMC-b388ff.svg)](#)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](#)

VITALSYNC is an edge-native personal health screening and early-warning platform designed to detect physiological anomalies and environmental strain before they escalate into acute emergencies. Deployable on edge gateways (such as a Raspberry Pi 4) paired with wearable multi-sensor nodes (ESP32), the system computes individual personal baselines, executes low-latency machine learning risk inference, applies trend persistence filtering, and broadcasts real-time telemetry to a medical-grade dashboard.

---

## Safety & Medical Framing Notice

> [!IMPORTANT]
> **This prototype provides health-risk and anomaly indicators. It is not a medical diagnostic device.**
> The system does not diagnose specific diseases (e.g. asthma or heat stroke). All outputs represent non-diagnostic screening levels: **Respiratory Risk**, **Physiological Anomaly**, **Heat-Stress Risk**, and **Environmental Exposure Risk**.

---

## Key Capabilities

### 1. Dual Operational Modes (Zero Frontend Mocking)
* **IoT LIVE MODE**: Real ESP32 microcontrollers stream multi-parametric sensor packets via HTTP POST or WebSocket into the edge backend.
* **SIMULATOR MODE**: For hardware-free development, testing, and clinical demonstrations. Sliders and scenario presets in the web interface stream directly to `POST /api/simulator/readings`. The simulator executes the **exact same feature extraction, baseline calculation, ML inference, escalation, and alert pipeline** as physical hardware.

### 2. Clinical Dataset Foundation
Trained directly on clinical hospital telemetry from the **PhysioNet BIDMC PPG and Respiration Dataset (v1.0.0)** (53 ICU patient recordings containing second-by-second ground-truth Heart Rate, Pulse, Respiration, and SpO2) combined with wearable multi-axis actigraphy (ADXL345) and environmental heat/gas exposure distributions.

### 3. Personal Baseline Engine
Replaces rigid universal thresholds with personalized rolling norms. Computes mean, median, standard deviation, Median Absolute Deviation (MAD), min, max, rolling baselines, and current deviations ($Z$-scores) for:
* Heart Rate
* SpO2
* Body Temperature
* Ambient Temperature & Humidity
* MQ-45 Environmental Air Quality Exposure

### 4. Trend-Based Early-Warning & Escalation Engine
* **Noise Dampening**: Single-reading spikes are filtered via a temporal persistence buffer (requiring multi-sample confirmation before critical escalation).
* **Multi-Parameter Escalation**: Concurrently deviating parameters (e.g., SpO2 drop + heart rate elevation + environmental gas spike) dynamically escalate risk levels from `EARLY_WARNING` $\to$ `ELEVATED` $\to$ `CRITICAL`.
* **Transparent Explainability**: Every risk score identifies its primary contributing features and relative deviations.

### 5. Caretaker Alert System
* Endpoints for dispatching, querying, and acknowledging caretaker alarms (`/api/alerts`).
* Tracks `alert_id`, `patient_id`, `timestamp`, `risk_type`, `risk_level`, `message`, `contributing_parameters`, GPS coordinates, and acknowledgment timestamp.
* Modular architecture ready for SMS, WhatsApp, and push notification webhooks.

---

## Hardware Parameters & Pinout

| Parameter | Source Sensor | Unit / Range | Edge Interface | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Heart Rate** | MAX30102 | 30–240 BPM | I2C (SDA:21, SCL:22) | Optical PPG heart rate |
| **SpO2** | MAX30102 | 60–100 % | I2C (SDA:21, SCL:22) | Capillary blood oxygen saturation |
| **PPG Signal Quality**| MAX30102 | 0.0 – 1.0 | Algorithm | AC/DC photoplethysmogram SNR |
| **Body Temperature** | DS18B20 / Thermal | 32.0–44.0 °C | OneWire (GPIO 4) | Core physiological body temperature |
| **Ambient Temperature**| DHT22 / AM2302 | -20.0–65.0 °C| Digital (GPIO 5) | Surrounding ambient temperature |
| **Ambient Humidity** | DHT22 / AM2302 | 0–100 % | Digital (GPIO 5) | Ambient relative humidity |
| **Acceleration X, Y, Z**| ADXL345 | $\pm 3.0$ g | I2C (SDA:21, SCL:22) | 3-axis motion & actigraphy |
| **MQ-45 Exposure** | MQ-45 / Gas Sensor | 0–2000 index | Analog ADC (GPIO 34)| Environmental air/gas exposure indicator |
| **GPS Location** | NEO-6M GPS | Lat / Lon | UART (RX:16, TX:17) | Wearable geographical coordinates |
| **Activity State** | Derived from ADXL345| REST / LIGHT / MODERATE / HIGH / FALL-CANDIDATE | Edge Actigraphy |

---

## Machine Learning Models (`backend/ml/models/`)

Four specialized edge-AI models are trained and serialized using Scikit-Learn and XGBoost:

| Model | Algorithm | Target Output | Validation Accuracy | F1-Macro |
| :--- | :--- | :--- | :---: | :---: |
| **Respiratory Risk Model** | XGBoost Classifier | Multi-Class (`LOW`, `EARLY_WARNING`, `ELEVATED`, `CRITICAL`) | **99.72%** | **0.9932** |
| **Heat-Stress Risk Model** | XGBoost Classifier | Multi-Class (`LOW`, `EARLY_WARNING`, `ELEVATED`, `CRITICAL`) | **99.68%** | **0.9923** |
| **Environmental Exposure Model** | GradientBoosting | Multi-Class (`LOW`, `EARLY_WARNING`, `ELEVATED`, `CRITICAL`) | **100.00%** | **1.0000** |
| **General Anomaly Model** | Ensemble XGBoost + IsolationForest | Binary Anomaly Detection (`NOMINAL`, `ANOMALOUS`) | **99.64%** | **0.9958** |

### Evaluated Risks Produced:
1. **General Health Anomaly Score**
2. **Respiratory Risk**
3. **Oxygenation Anomaly**
4. **Heat-Stress / Physiological-Strain Risk**
5. **Fatigue / Activity-Strain Risk**
6. **Environmental Exposure Risk**
7. **Overall Health Risk**

---

## Repository Structure

```
SIH 2026/
├── Datasets/
│   └── bidmc-ppg-and-respiration-dataset-1.0.0/  # Real PhysioNet clinical data
├── backend/
│   ├── main.py                    # FastAPI app entry point & WebSocket /ws/live
│   ├── api/
│   │   ├── routes.py              # REST endpoints (sensors, simulator, ML, alerts)
│   │   ├── schemas.py             # Pydantic data schemas
│   │   └── websocket_manager.py   # WebSocket telemetry broadcaster
│   ├── core/
│   │   ├── baseline_engine.py     # Personal baseline tracker (mean, MAD, deviations)
│   │   ├── early_warning_engine.py# Trend persistence & multi-parameter escalation
│   │   └── alert_engine.py        # Caretaker notification lifecycle & acknowledgments
│   ├── db/
│   │   └── database.py            # MongoDB storage layer with mongomock fallback
│   └── ml/
│       ├── dataset_loader.py      # BIDMC clinical data parser & multimodal synthesis
│       ├── train_models.py        # Model training pipeline
│       ├── evaluate_models.py     # Model evaluation & confusion matrix generator
│       ├── feature_engine.py      # Physics, actigraphy, and baseline feature extraction
│       ├── model_registry.py      # Multi-model inference suite & explainability
│       └── models/                # Serialized model artifacts (.joblib, .json)
├── firmware/
│   ├── esp32_real_sensors.ino     # Production C++ Arduino firmware for 6 real sensors
│   └── esp32_hardware_emulator.py # Python daemon simulating physical ESP32
├── testing-ui/                    # Smartwatch Testing & Edge-AI Simulation Lab (Port 2134)
├── user-ui/                       # Wearable Health Companion & Patient POV UI (Port 3000)
├── start.bat                      # Unified single-click launcher
├── test_scenarios.py              # Automated 9-part end-to-end verification test suite
├── requirements.txt               # Pinned dependencies
├── .env.example                   # Environment configuration template
└── README.md                      # Comprehensive documentation
```

---

## API Reference

### Sensor Telemetry & Simulation
* `POST /api/sensors/readings`: Ingests physical IoT readings from ESP32.
* `GET /api/sensors/latest`: Returns the most recent sensor reading.
* `POST /api/simulator/readings`: Ingests simulator readings (runs identical ML/alert pipeline).

### Machine Learning & Risk Inference
* `POST /api/ml/predict`: Runs unified feature extraction and ML risk scoring.
* `GET /api/ml/latest`: Returns latest ML predictions.
* `GET /api/risk/current`: Returns current escalated risk level and contributing reasons.
* `GET /api/risk/history`: Returns historical risk events.

### Personal Baseline
* `POST /api/baseline/start`: Initiates a clean personal baseline calibration period.
* `POST /api/baseline/update`: Manually refines baseline with a specific reading.
* `GET /api/baseline`: Returns baseline statistics, MAD, and current deviations.

### Caretaker Alerts
* `POST /api/alerts`: Dispatches a manual or automated caretaker alert.
* `GET /api/alerts`: Returns alert history log.
* `GET /api/alerts/latest`: Returns active/latest caretaker notification.
* `POST /api/alerts/{id}/acknowledge`: Acknowledges an alert with timestamp.

### Device & System
* `POST /api/device/register`: Registers edge device and patient metadata.
* `GET /api/health`: Edge system status, loaded model versions, and connection state.
* `WebSocket /ws/live`: Real-time bidirectional telemetry and alert streaming.

---

## Quickstart Guide

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Train or Verify Models
The models have already been trained and serialized to `backend/ml/models/`. You can re-train or evaluate them at any time:
```bash
python -m backend.ml.train_models
python -m backend.ml.evaluate_models
```

### 3. Run the Automated Test Suite
```bash
python test_scenarios.py
```
*Validates health, device registration, baseline calculation, normal/early/elevated/critical scenarios, caretaker alerts, alert acknowledgments, simulator symmetry, and MongoDB data traceability.*

### 4. Start the Edge API Server
```bash
python backend/main.py
# Or using uvicorn:
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Open the Web Dashboard
Navigate to `http://localhost:8000` in any web browser.

### 6. Interactive Testing Walkthrough
1. **Enable Simulator Mode**: Click the **SIMULATOR** button in the header.
2. **Preset Scenarios**: Click preset buttons (e.g. *Early Respiratory*, *Heat-Stress*, *Critical Multi-Parameter*).
3. **Manual Adjustments**: Slide Heart Rate or SpO2 sliders and observe live values update in milliseconds.
4. **Inspect Pipeline**: Scroll to the **REAL-TIME TEST MODE** panel to trace:
   $$\text{INPUT} \longrightarrow \text{FEATURES} \longrightarrow \text{MODEL SCORES} \longrightarrow \text{ESCALATED RISK} \longrightarrow \text{CARETAKER ALERT}$$
5. **Caretaker Alert & Acknowledgment**: When risk escalates to `CRITICAL`, the high-priority Caretaker Notification Banner will appear. Click **Acknowledge Alert** to confirm and record the action in the database.
6. **Switch to IoT Mode**: Click **IoT LIVE** to stream physical ESP32 or simulated daemon telemetry (`python firmware/esp32_hardware_emulator.py`).
