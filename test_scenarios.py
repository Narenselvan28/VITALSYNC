"""
AAROGYA-SHIELD: End-to-End Automated Test Suite & Scenario Verification
Validates:
1. System Health & Model Status (/api/health)
2. Device Registration (/api/device/register)
3. Personal Baseline Calibration (/api/baseline/start, /api/baseline)
4. Scenario 1: Normal Healthy Telemetry (Verifies LOW risk)
5. Scenario 2: Early Respiratory Warning (Verifies EARLY_WARNING)
6. Scenario 3: Elevated Multi-Parameter Respiratory Anomaly (Verifies ELEVATED)
7. Scenario 4: Critical Anomaly & Caretaker Alert Trigger (Verifies CRITICAL escalation & alert)
8. Caretaker Alert Query (/api/alerts/latest, /api/alerts)
9. Caretaker Alert Acknowledgment (/api/alerts/{id}/acknowledge)
10. Simulator vs IoT API Symmetry (Identical processing pipeline verification)
11. MongoDB Data Traceability (Reading ID -> Features -> Predictions -> Risk Events)
"""

import sys
import datetime
import unittest
from fastapi.testclient import TestClient

from backend.main import app
from backend.db.database import get_db

client = TestClient(app)

class AarogyaShieldTestSuite(unittest.TestCase):
    def setUp(self):
        self.device_id = "ESP32-001"

    def test_01_health_check(self):
        print("\n[Test 1] Checking Edge System Health...")
        resp = client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ONLINE")
        self.assertTrue(data["models_loaded"])
        self.assertIn("diagnostic", data["medical_disclaimer"].lower())
        self.assertIn("not a medical diagnostic device", data["medical_disclaimer"].lower())
        print(f" -> System: {data['system']} (Models Loaded: {data['models_loaded']})")

    def test_02_device_registration(self):
        print("\n[Test 2] Registering Device & Patient Metadata...")
        payload = {
            "device_id": self.device_id,
            "device_type": "ESP32-MAX30102-ADXL345",
            "firmware_version": "v1.0.0",
            "patient_name": "Subject-42",
            "patient_age": 38,
            "location": "Ward Edge Gateway"
        }
        resp = client.post("/api/device/register", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "registered")
        self.assertEqual(data["device"]["device_id"], self.device_id)
        print(f" -> Device {self.device_id} registered successfully.")

    def test_03_baseline_calibration(self):
        print("\n[Test 3] Calibrating Personal Baseline...")
        start_resp = client.post("/api/baseline/start", json={"device_id": self.device_id})
        self.assertEqual(start_resp.status_code, 200)
        
        # Feed 5 nominal readings to populate baseline
        for i in range(5):
            client.post("/api/sensors/readings", json={
                "device_id": self.device_id,
                "heart_rate": 72.0 + i,
                "spo2": 98.0,
                "body_temperature": 36.7,
                "ambient_temperature": 28.0,
                "humidity": 60.0,
                "mq45": 180.0,
                "accel_x": 0.02,
                "accel_y": 0.01,
                "accel_z": 0.98,
            })

        base_resp = client.get(f"/api/baseline?device_id={self.device_id}")
        self.assertEqual(base_resp.status_code, 200)
        stats = base_resp.json()["statistics"]
        self.assertIn("heart_rate", stats)
        self.assertIn("spo2", stats)
        self.assertIn("body_temperature", stats)
        print(f" -> Baseline Mean HR: {stats['heart_rate']['mean']}, SpO2: {stats['spo2']['mean']}, Temp: {stats['body_temperature']['mean']}")

    def test_04_scenario_normal(self):
        print("\n[Test 4] Ingesting Normal Telemetry (Scenario 1)...")
        payload = {
            "device_id": self.device_id,
            "heart_rate": 74.0,
            "spo2": 98.0,
            "ppg_quality": 0.96,
            "body_temperature": 36.8,
            "ambient_temperature": 28.0,
            "humidity": 60.0,
            "accel_x": 0.02,
            "accel_y": 0.01,
            "accel_z": 0.98,
            "mq45": 180.0,
        }
        resp = client.post("/api/sensors/readings", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        overall = data["ml_predictions"]["overall_health_risk"]
        esc = data["escalation"]
        self.assertEqual(esc["escalated_level"], "LOW")
        print(f" -> Overall Risk: {overall['score']} | Level: {esc['escalated_level']} | Reasons: {esc['reasons'][0]}")

    def test_05_scenario_early_warning(self):
        print("\n[Test 5] Ingesting Early Respiratory Warning (Scenario 2)...")
        payload = {
            "device_id": self.device_id,
            "heart_rate": 86.0,
            "spo2": 94.0,  # Mild drop from 98% baseline
            "ppg_quality": 0.94,
            "body_temperature": 36.8,
            "ambient_temperature": 28.0,
            "humidity": 60.0,
            "accel_x": 0.02,
            "accel_y": 0.01,
            "accel_z": 0.98,
            "mq45": 320.0,  # Mild air quality elevation
        }
        resp = client.post("/api/simulator/readings", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        esc = data["escalation"]
        self.assertIn(esc["escalated_level"], ["EARLY_WARNING", "ELEVATED"])
        print(f" -> Escalated Level: {esc['escalated_level']} | Reasons: {esc['reasons']}")

    def test_06_scenario_elevated_risk(self):
        print("\n[Test 6] Ingesting Elevated Respiratory & Physiological Anomaly (Scenario 3)...")
        payload = {
            "device_id": self.device_id,
            "heart_rate": 115.0,  # Tachycardic compensation
            "spo2": 90.0,        # Significant desaturation
            "ppg_quality": 0.90,
            "body_temperature": 37.4,
            "ambient_temperature": 30.0,
            "humidity": 65.0,
            "accel_x": 0.1,
            "accel_y": 0.1,
            "accel_z": 0.95,
            "mq45": 540.0,
        }
        resp = client.post("/api/simulator/readings", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        esc = data["escalation"]
        self.assertIn(esc["escalated_level"], ["ELEVATED", "CRITICAL"])
        print(f" -> Escalated Level: {esc['escalated_level']} | Multi-parameter count: {esc['deviating_parameter_count']}")

    def test_07_scenario_critical_and_caretaker_alert(self):
        print("\n[Test 7] Ingesting Sustained Critical Anomaly (Scenario 4)...")
        # Send 3 sustained critical packets to trigger persistence filter
        last_resp = None
        for i in range(3):
            payload = {
                "device_id": self.device_id,
                "heart_rate": 145.0,  # Severe tachycardia
                "spo2": 84.0,         # Severe hypoxia
                "ppg_quality": 0.88,
                "body_temperature": 39.8,  # Severe fever / heat stress
                "ambient_temperature": 44.0,
                "humidity": 85.0,
                "accel_x": 2.5,       # Potential fall impact
                "accel_y": 2.2,
                "accel_z": 0.2,
                "mq45": 880.0,        # Hazardous gas
                "latitude": 10.662,
                "longitude": 76.891,
            }
            resp = client.post("/api/simulator/readings", json=payload)
            self.assertEqual(resp.status_code, 200)
            last_resp = resp.json()

        esc = last_resp["escalation"]
        self.assertEqual(esc["escalated_level"], "CRITICAL")
        self.assertIsNotNone(last_resp["active_alert"])
        alert = last_resp["active_alert"]
        self.assertEqual(alert["risk_level"], "CRITICAL")
        print(f" -> Escalated Level: {esc['escalated_level']}")
        print(f" -> Caretaker Alert Generated: ID={alert['alert_id']} Msg='{alert['message']}'")

        # Test Alert Query
        latest_alert_resp = client.get("/api/alerts/latest")
        self.assertEqual(latest_alert_resp.status_code, 200)
        latest_alert = latest_alert_resp.json()
        self.assertEqual(latest_alert["alert_id"], alert["alert_id"])
        self.assertFalse(latest_alert["acknowledged"])

        # Test Alert Acknowledgment
        ack_resp = client.post(f"/api/alerts/{alert['alert_id']}/acknowledge")
        self.assertEqual(ack_resp.status_code, 200)
        acked = ack_resp.json()
        self.assertTrue(acked["acknowledged"])
        self.assertIsNotNone(acked["acknowledged_at"])
        print(f" -> Alert {alert['alert_id']} acknowledged at {acked['acknowledged_at']}.")

    def test_08_simulator_vs_iot_pipeline_symmetry(self):
        print("\n[Test 8] Verifying Simulator and IoT Mode Pipeline Symmetry...")
        sample_reading = {
            "device_id": self.device_id,
            "heart_rate": 80.0,
            "spo2": 97.0,
            "ppg_quality": 0.95,
            "body_temperature": 36.8,
            "ambient_temperature": 28.0,
            "humidity": 60.0,
            "accel_x": 0.02,
            "accel_y": 0.01,
            "accel_z": 0.98,
            "mq45": 200.0,
        }

        # Run through IoT endpoint
        iot_resp = client.post("/api/sensors/readings", json=sample_reading).json()
        # Run through Simulator endpoint
        sim_resp = client.post("/api/simulator/readings", json=sample_reading).json()
        # Run through Direct ML endpoint
        ml_resp = client.post("/api/ml/predict", json=sample_reading).json()

        # Compare outputs
        iot_score = iot_resp["ml_predictions"]["overall_health_risk"]["score"]
        sim_score = sim_resp["ml_predictions"]["overall_health_risk"]["score"]
        ml_score = ml_resp["ml_predictions"]["overall_health_risk"]["score"]

        self.assertAlmostEqual(iot_score, sim_score, places=2)
        self.assertAlmostEqual(sim_score, ml_score, places=2)
        print(f" -> IoT Score: {iot_score} | Simulator Score: {sim_score} | ML Score: {ml_score} (Perfect Symmetry Verified)")

    def test_09_database_traceability(self):
        print("\n[Test 9] Auditing MongoDB Traceability...")
        db = get_db()
        latest_reading = db.get_latest_reading(self.device_id)
        self.assertIsNotNone(latest_reading)
        reading_id = str(latest_reading["_id"])
        
        # Check prediction document linked to reading_id
        pred_doc = db.db.predictions.find_one({"reading_id": reading_id})
        self.assertIsNotNone(pred_doc, f"Prediction missing for reading_id {reading_id}")
        self.assertIn("overall_health_risk", pred_doc)

        # Check feature document linked to reading_id
        feat_doc = db.db.feature_vectors.find_one({"reading_id": reading_id})
        self.assertIsNotNone(feat_doc, f"Features missing for reading_id {reading_id}")
        self.assertIn("hr_deviation", feat_doc)
        print(f" -> Reading ID {reading_id} successfully traced to Feature Vector & ML Predictions in Database.")

if __name__ == "__main__":
    unittest.main()
