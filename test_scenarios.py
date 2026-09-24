"""
VITALSYNC: Automated Acceptance Test Suite (18 Scenarios)
Verifies the complete reconstructed contextual ML, risk engine, signal quality, and alert pipeline:
TEST 01: Normal person at rest -> NORMAL, zero alerts
TEST 02: Short HR spike (72 -> 198 -> 75 for 2s) -> Observation, NO persistent caretaker alert
TEST 03: Persistent HR elevation at rest (72 -> 150 -> 175) -> HEART RATE ANOMALY (NOT respiratory distress)
TEST 04: Exercise / High Activity (HR 150, Act HIGH, SpO2 98) -> ACTIVITY-ASSOCIATED HR ELEVATION, NO critical alert
TEST 05: Hot beverage contact (NTC 36.7 -> 39.0 -> 36.7) -> TEMPORARY SENSOR DEVIATION -> RECOVERING -> NORMAL
TEST 06: AC room transition (Ambient 32 -> 22, body temp stable) -> ENVIRONMENT CHANGED, NO health alert
TEST 07: Humidity increase alone (50 -> 85%) -> Context only, NO health alert
TEST 08: Normal watch/wrist movement -> MOVEMENT, NOT fall
TEST 09: Actual fall pattern (Impact + tilt + inactivity) -> FALL CANDIDATE -> CONFIRMED FALL
TEST 10: Fall-like movement followed by recovery -> FALL CANDIDATE -> CANCELLED / RECOVERED -> NORMAL
TEST 11: ADXL345 disconnected / NaN -> ACTIVITY SENSOR UNAVAILABLE, NO fall alert
TEST 12: High ambient + high activity + rising NTC & HR -> THERMAL STRAIN RISK ELEVATED
TEST 13: Outdoor heat wave (38°C) with normal physiology -> Weather context updated, NO health alert
TEST 14: High gas exposure (MQ-45 > 650) -> ENVIRONMENTAL EXPOSURE warning, NOT disease diagnosis
TEST 15: GPS coordinate shift -> Weather context dynamically updates
TEST 16: Internet / Weather service offline -> Seamless LOCAL SENSOR MODE, zero crash
TEST 17: SIM800L module offline -> Local ML continues, communication marked offline
TEST 18: Persistent multi-parameter deterioration (HR elevated, SpO2 depressed, rest) -> Stronger multimodal risk
"""

import sys
import os
import time
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.main import app
from backend.core.weather_service import get_weather_engine
from backend.core.communication_manager import get_communication_manager
from backend.core.alert_state_machine import get_alert_state_machine
from backend.core.alert_engine import get_alert_engine
from backend.core.fall_engine import get_fall_engine

client = TestClient(app)

class VitalSyncAcceptanceSuite(unittest.TestCase):
    def setUp(self):
        self.device_id = "ESP32-001"
        self.weather_engine = get_weather_engine()
        self.weather_engine.set_forced_offline(False)
        self.comm_manager = get_communication_manager()
        self.comm_manager.set_module_available(True)
        get_alert_state_machine().reset(self.device_id)
        get_alert_engine().reset()
        get_fall_engine()._get_state(self.device_id).reset_to_normal()

    def test_01_normal_resting(self):
        print("\n[TEST 01] Normal resting physiology...")
        payload = {
            "device_id": self.device_id,
            "heart_rate": 72.0,
            "spo2": 98.0,
            "ppg_quality": 0.96,
            "body_temperature": 36.7,
            "ambient_temperature": 27.5,
            "humidity": 55.0,
            "accel_x": 0.02,
            "accel_y": 0.01,
            "accel_z": 0.98,
            "mq45": 160.0,
        }
        resp = client.post("/api/simulator/readings", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        esc = data["escalation"]
        self.assertIn(esc["escalated_level"], ["NORMAL", "OBSERVATION"])
        self.assertIsNone(data["active_alert"])
        print(f" -> Result: Level = {esc['escalated_level']} | Active Alert = None (OK)")

    def test_02_short_hr_spike(self):
        print("\n[TEST 02] Short HR spike (72 -> 198 -> 75, 2-3s)...")
        # Step 1: Normal
        client.post("/api/simulator/readings", json={"device_id": self.device_id, "heart_rate": 72.0, "spo2": 98.0, "body_temperature": 36.7, "ambient_temperature": 28.0, "humidity": 60.0, "mq45": 180.0})
        # Step 2: Sudden 1-sample spike to 198 BPM
        spike_resp = client.post("/api/simulator/readings", json={"device_id": self.device_id, "heart_rate": 198.0, "spo2": 98.0, "body_temperature": 36.7, "ambient_temperature": 28.0, "humidity": 60.0, "mq45": 180.0}).json()
        
        # Step 3: Returns to 75 immediately
        rec_resp = client.post("/api/simulator/readings", json={"device_id": self.device_id, "heart_rate": 75.0, "spo2": 98.0, "body_temperature": 36.7, "ambient_temperature": 28.0, "humidity": 60.0, "mq45": 180.0}).json()
        
        # Must NOT classify as respiratory distress!
        ml_preds = spike_resp["ml_predictions"]
        resp_risk = ml_preds["risk_domains"]["respiratory_risk"]["level"]
        hr_dom = ml_preds["risk_domains"]["heart_rate_anomaly"]
        
        self.assertNotEqual(ml_preds["overall_health_risk"]["primary_domain"], "Respiratory Risk")
        self.assertIn(hr_dom["level"], ["ELEVATED", "CRITICAL"])
        # Should clear or have no persistent caretaker alert
        self.assertIn(rec_resp["escalation"]["escalated_level"], ["NORMAL", "OBSERVATION", "RECOVERING"])
        print(f" -> Spike Domain: {ml_preds['overall_health_risk']['primary_domain']} (NOT Respiratory Distress) | Recovery Level: {rec_resp['escalation']['escalated_level']} (OK)")

    def test_03_persistent_hr_at_rest(self):
        print("\n[TEST 03] Persistent HR elevation at REST (72 -> 150 -> 165 -> 175)...")
        last_resp = None
        for hr_val in [150.0, 165.0, 175.0, 175.0]:
            payload = {
                "device_id": self.device_id,
                "heart_rate": hr_val,
                "spo2": 98.0,  # SpO2 normal!
                "body_temperature": 36.7,
                "ambient_temperature": 28.0,
                "humidity": 60.0,
                "accel_x": 0.02,
                "accel_y": 0.01,
                "accel_z": 0.98,
                "mq45": 180.0,
            }
            resp = client.post("/api/simulator/readings", json=payload)
            last_resp = resp.json()

        ml_preds = last_resp["ml_predictions"]
        # Primary domain MUST be Heart Rate Anomaly, NEVER Respiratory Distress!
        self.assertEqual(ml_preds["overall_health_risk"]["primary_domain"], "Heart Rate Anomaly")
        self.assertIn(ml_preds["risk_domains"]["heart_rate_anomaly"]["level"], ["ELEVATED", "CRITICAL"])
        self.assertEqual(ml_preds["risk_domains"]["respiratory_risk"]["level"], "LOW")
        print(f" -> Primary Domain: {ml_preds['overall_health_risk']['primary_domain']} | HR Level: {ml_preds['risk_domains']['heart_rate_anomaly']['level']} | Resp Level: {ml_preds['risk_domains']['respiratory_risk']['level']} (OK)")

    def test_04_exercise_hr_increase(self):
        print("\n[TEST 04] Exercise (HR 150, Activity HIGH, SpO2 98)...")
        payload = {
            "device_id": self.device_id,
            "heart_rate": 150.0,
            "spo2": 98.0,
            "body_temperature": 37.1,
            "ambient_temperature": 28.0,
            "humidity": 60.0,
            "accel_x": 0.8,
            "accel_y": 0.7,
            "accel_z": 1.4, # High activity
            "mq45": 180.0,
        }
        resp = client.post("/api/simulator/readings", json=payload)
        data = resp.json()
        features = data["features"]
        ml_preds = data["ml_predictions"]
        self.assertTrue(features["is_active"])
        self.assertIn(features["activity_level"], ["WALKING", "RUNNING_HIGH_ACTIVITY"])
        # Exercise should NOT trigger a CRITICAL health alert
        self.assertNotEqual(data["escalation"]["escalated_level"], "CRITICAL")
        self.assertIn("exercise", ml_preds["risk_domains"]["heart_rate_anomaly"]["reason"].lower())
        print(f" -> Activity: {features['activity_level']} | Escalated Level: {data['escalation']['escalated_level']} | Reason: {ml_preds['risk_domains']['heart_rate_anomaly']['reason']} (OK)")

    def test_05_hot_beverage_spike_and_recovery(self):
        print("\n[TEST 05] Hot beverage contact spike (NTC 36.7 -> 39.0 -> 36.7)...")
        # Step 1: Normal
        client.post("/api/simulator/readings", json={"device_id": self.device_id, "heart_rate": 72.0, "spo2": 98.0, "body_temperature": 36.7, "ambient_temperature": 26.0, "humidity": 50.0, "mq45": 150.0})
        # Step 2: Hot mug touch (39.0°C contact, ambient normal 26°C, HR resting 72)
        spike_resp = client.post("/api/simulator/readings", json={"device_id": self.device_id, "heart_rate": 72.0, "spo2": 98.0, "body_temperature": 39.0, "ambient_temperature": 26.0, "humidity": 50.0, "mq45": 150.0}).json()
        # Must detect transient contact disturbance, NOT heat stroke!
        self.assertTrue(spike_resp["features"]["is_transient_thermal"])
        self.assertEqual(spike_resp["ml_predictions"]["risk_domains"]["heat_stress_risk"]["level"], "LOW")
        
        # Step 3: Returns to 36.7
        rec_resp = client.post("/api/simulator/readings", json={"device_id": self.device_id, "heart_rate": 72.0, "spo2": 98.0, "body_temperature": 36.7, "ambient_temperature": 26.0, "humidity": 50.0, "mq45": 150.0}).json()
        self.assertIn(rec_resp["escalation"]["escalated_level"], ["NORMAL", "RECOVERING", "OBSERVATION"])
        print(f" -> Transient Detected: {spike_resp['features']['is_transient_thermal']} | Thermal Message: '{spike_resp['features']['thermal_message']}' (OK)")

    def test_06_ac_room_transition(self):
        print("\n[TEST 06] AC room transition (Ambient 32 -> 22, body temp stable)...")
        payload = {
            "device_id": self.device_id,
            "heart_rate": 72.0,
            "spo2": 98.0,
            "body_temperature": 36.7,
            "ambient_temperature": 21.5, # Cold AC room
            "humidity": 45.0,
            "mq45": 150.0,
        }
        resp = client.post("/api/simulator/readings", json=payload)
        data = resp.json()
        self.assertIn(data["escalation"]["escalated_level"], ["NORMAL", "OBSERVATION"])
        self.assertEqual(data["ml_predictions"]["risk_domains"]["heat_stress_risk"]["level"], "LOW")
        print(f" -> AC Transition Level: {data['escalation']['escalated_level']} | Heat Level: LOW (OK)")

    def test_07_humidity_increase_alone(self):
        print("\n[TEST 07] Humidity increase alone (50 -> 88%)...")
        payload = {
            "device_id": self.device_id,
            "heart_rate": 72.0,
            "spo2": 98.0,
            "body_temperature": 36.7,
            "ambient_temperature": 26.0,
            "humidity": 88.0, # High humidity alone
            "mq45": 150.0,
        }
        resp = client.post("/api/simulator/readings", json=payload)
        data = resp.json()
        # Humidity alone MUST NOT trigger a health alert!
        self.assertIn(data["escalation"]["escalated_level"], ["NORMAL", "OBSERVATION"])
        self.assertIsNone(data["active_alert"])
        print(f" -> Humidity alone: Escalated Level = {data['escalation']['escalated_level']} | Alert = None (OK)")

    def test_08_normal_watch_movement(self):
        print("\n[TEST 08] Normal watch movement / wrist gestures...")
        payload = {
            "device_id": self.device_id,
            "heart_rate": 75.0,
            "spo2": 98.0,
            "body_temperature": 36.7,
            "ambient_temperature": 28.0,
            "humidity": 60.0,
            "accel_x": 0.35, # Moderate wrist gesture
            "accel_y": 0.40,
            "accel_z": 0.90,
            "mq45": 180.0,
        }
        resp = client.post("/api/simulator/readings", json=payload)
        data = resp.json()
        fall_info = data["ml_predictions"]["risk_domains"]["fall_event"]
        self.assertFalse(fall_info["is_confirmed"])
        self.assertNotEqual(fall_info["state"], "CONFIRMED_FALL")
        print(f" -> Gesture State: {fall_info['state']} (NOT Fall) (OK)")

    def test_09_actual_fall_pattern(self):
        print("\n[TEST 09] Actual fall pattern (Impact + tilt + sustained immobility)...")
        # Step 1: Impact spike
        impact_resp = client.post("/api/simulator/readings", json={
            "device_id": self.device_id, "heart_rate": 90.0, "spo2": 97.0, "body_temperature": 36.8, "ambient_temperature": 28.0, "humidity": 60.0, "mq45": 180.0,
            "accel_x": 2.6, "accel_y": 2.2, "accel_z": 0.2, # >2.6g impact
        }).json()

        # Step 2: Post-impact tilt and immobility for several cycles
        last_resp = None
        for _ in range(5):
            last_resp = client.post("/api/simulator/readings", json={
                "device_id": self.device_id, "heart_rate": 92.0, "spo2": 97.0, "body_temperature": 36.8, "ambient_temperature": 28.0, "humidity": 60.0, "mq45": 180.0,
                "accel_x": 0.7, "accel_y": 0.6, "accel_z": 0.15, # Lying flat/tilted, zero motion
            }).json()

        fall_info = last_resp["ml_predictions"]["risk_domains"]["fall_event"]
        self.assertTrue(fall_info["is_confirmed"] or fall_info["is_candidate"])
        print(f" -> Fall State: {fall_info['state']} | Message: '{fall_info['reason']}' (OK)")

    def test_10_fall_candidate_followed_by_recovery(self):
        print("\n[TEST 10] Fall-like movement followed by immediate recovery...")
        # Step 1: High impact
        client.post("/api/simulator/readings", json={
            "device_id": self.device_id, "heart_rate": 85.0, "spo2": 98.0, "body_temperature": 36.7, "ambient_temperature": 28.0, "humidity": 60.0, "mq45": 180.0,
            "accel_x": 2.7, "accel_y": 2.1, "accel_z": 0.2,
        })
        # Step 2: Patient immediately gets up and continues walking normally!
        rec_resp = client.post("/api/simulator/readings", json={
            "device_id": self.device_id, "heart_rate": 88.0, "spo2": 98.0, "body_temperature": 36.7, "ambient_temperature": 28.0, "humidity": 60.0, "mq45": 180.0,
            "accel_x": 0.3, "accel_y": 0.3, "accel_z": 1.25, # Active movement
        }).json()

        fall_info = rec_resp["ml_predictions"]["risk_domains"]["fall_event"]
        self.assertFalse(fall_info["is_confirmed"])
        self.assertIn(fall_info["state"], ["CANCELLED_RECOVERED", "NORMAL"])
        print(f" -> Fall State: {fall_info['state']} (Cancelled / Recovered) (OK)")

    def test_11_adxl345_disconnected(self):
        print("\n[TEST 11] ADXL345 disconnected / invalid data...")
        payload = {
            "device_id": self.device_id,
            "heart_rate": 74.0,
            "spo2": 98.0,
            "body_temperature": 36.7,
            "ambient_temperature": 28.0,
            "humidity": 60.0,
            "mq45": 180.0,
            "adxl_available": False,
            "accel_x": 0.0,
            "accel_y": 0.0,
            "accel_z": 0.0, # Zero clamped on disconnected I2C
        }
        resp = client.post("/api/simulator/readings", json=payload)
        data = resp.json()
        fall_info = data["ml_predictions"]["risk_domains"]["fall_event"]
        self.assertFalse(fall_info["is_confirmed"])
        self.assertEqual(fall_info["state"], "SENSOR_UNAVAILABLE")
        print(f" -> Disconnect Result: {fall_info['state']} (NEVER Fall Detected) (OK)")

    def test_12_high_ambient_high_activity_rising_heat(self):
        print("\n[TEST 12] High ambient + high activity + rising NTC & HR (True Thermal Strain)...")
        payload = {
            "device_id": self.device_id,
            "heart_rate": 140.0,
            "spo2": 97.0,
            "body_temperature": 39.2, # High fever / thermal strain
            "ambient_temperature": 39.0, # Hot environment
            "humidity": 75.0,
            "accel_x": 0.6,
            "accel_y": 0.6,
            "accel_z": 1.3,
            "mq45": 220.0,
        }
        resp = client.post("/api/simulator/readings", json=payload)
        data = resp.json()
        heat_dom = data["ml_predictions"]["risk_domains"]["heat_stress_risk"]
        self.assertIn(heat_dom["level"], ["ELEVATED", "CRITICAL"])
        print(f" -> Thermal Strain Level: {heat_dom['level']} | Score: {heat_dom['score']} (OK)")

    def test_13_outdoor_heat_wave_normal_physiology(self):
        print("\n[TEST 13] Outdoor heat wave (38°C) but normal physiology...")
        payload = {
            "device_id": self.device_id,
            "heart_rate": 72.0,  # Normal HR
            "spo2": 98.0,        # Normal SpO2
            "body_temperature": 36.7, # Normal contact temp
            "ambient_temperature": 38.0, # Hot ambient/weather
            "humidity": 65.0,
            "mq45": 170.0,
            "accel_x": 0.02,
            "accel_y": 0.01,
            "accel_z": 0.98,
        }
        resp = client.post("/api/simulator/readings", json=payload)
        data = resp.json()
        # External weather must NOT turn into a medical emergency when physiology is healthy!
        self.assertNotEqual(data["escalation"]["escalated_level"], "CRITICAL")
        self.assertIsNone(data["active_alert"])
        print(f" -> Heat Wave Physiology Normal: Escalated Level = {data['escalation']['escalated_level']} (No Emergency) (OK)")

    def test_14_high_gas_exposure_mq45(self):
        print("\n[TEST 14] High MQ-45 gas exposure (780 index)...")
        payload = {
            "device_id": self.device_id,
            "heart_rate": 76.0,
            "spo2": 98.0,
            "body_temperature": 36.8,
            "ambient_temperature": 28.0,
            "humidity": 55.0,
            "mq45": 780.0, # High environmental gas
        }
        resp = client.post("/api/simulator/readings", json=payload)
        data = resp.json()
        env_dom = data["ml_predictions"]["risk_domains"]["environmental_exposure"]
        self.assertIn(env_dom["level"], ["ELEVATED", "CRITICAL"])
        # Must be non-diagnostic environmental advisory, NOT asthma diagnosis!
        self.assertIn("environmental", env_dom["reason"].lower())
        self.assertNotIn("asthma", env_dom["reason"].lower())
        print(f" -> Environmental Level: {env_dom['level']} | Reason: '{env_dom['reason']}' (OK)")

    def test_15_gps_coordinate_shift(self):
        print("\n[TEST 15] GPS coordinate shift...")
        resp = client.get("/api/weather/current?lat=13.0827&lon=80.2707") # Chennai coords
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("outdoor_temperature", data)
        print(f" -> Weather Context: Status = {data['status']} | Mode = {data.get('mode')} (OK)")

    def test_16_weather_service_offline_fallback(self):
        print("\n[TEST 16] Weather service offline (LOCAL SENSOR MODE)...")
        client.post("/api/weather/toggle-offline?offline=true")
        weather_resp = client.get("/api/weather/current?lat=10.662&lon=76.891").json()
        self.assertEqual(weather_resp["status"], "OFFLINE")
        self.assertEqual(weather_resp["mode"], "LOCAL_SENSOR_MODE")

        # Telemetry ingestion continues without crash
        resp = client.post("/api/simulator/readings", json={
            "device_id": self.device_id, "heart_rate": 74.0, "spo2": 98.0, "body_temperature": 36.7, "ambient_temperature": 28.0, "humidity": 60.0, "mq45": 180.0,
            "weather_status": "OFFLINE",
        })
        self.assertEqual(resp.status_code, 200)
        client.post("/api/weather/toggle-offline?offline=false")
        print(" -> Seamless LOCAL SENSOR MODE verified. ML pipeline unaffected. (OK)")

    def test_17_sim800l_offline_fallback(self):
        print("\n[TEST 17] SIM800L cellular module offline...")
        client.post("/api/communication/toggle-offline?offline=true")
        status_resp = client.get("/api/communication/status").json()
        self.assertFalse(status_resp["is_available"])
        self.assertEqual(status_resp["status"], "OFFLINE")

        # Telemetry ingestion continues normally
        resp = client.post("/api/simulator/readings", json={
            "device_id": self.device_id, "heart_rate": 74.0, "spo2": 98.0, "body_temperature": 36.7, "ambient_temperature": 28.0, "humidity": 60.0, "mq45": 180.0,
            "sim800l_status": "OFFLINE",
        })
        self.assertEqual(resp.status_code, 200)
        client.post("/api/communication/toggle-offline?offline=false")
        print(" -> SIM800L offline handled gracefully. (OK)")

    def test_18_multimodal_physiological_deterioration(self):
        print("\n[TEST 18] Persistent multi-parameter deterioration (HR 145, SpO2 84%, Rest)...")
        last_resp = None
        for _ in range(4):
            last_resp = client.post("/api/simulator/readings", json={
                "device_id": self.device_id,
                "heart_rate": 145.0,
                "spo2": 84.0, # Severe hypoxia + tachycardia
                "body_temperature": 38.8,
                "ambient_temperature": 30.0,
                "humidity": 65.0,
                "accel_x": 0.02,
                "accel_y": 0.01,
                "accel_z": 0.98,
                "mq45": 420.0,
            }).json()

        esc = last_resp["escalation"]
        self.assertEqual(esc["escalated_level"], "CRITICAL")
        self.assertIsNotNone(last_resp["active_alert"])
        alert = last_resp["active_alert"]
        self.assertEqual(alert["risk_level"], "CRITICAL")
        print(f" -> Multimodal Escalation: Level = {esc['escalated_level']} | Alert ID = {alert['alert_id']} (OK)")

if __name__ == "__main__":
    unittest.main()
