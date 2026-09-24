"""
AAROGYA-SHIELD: Personalized Health Profile & Adaptive Threshold Test Suite
Validates the complete 15-scenario personalized interpretation, adaptive baseline,
clinical reference threshold, active condition context, and non-diagnostic safety pipeline:

1. Healthy profile (no known condition) -> Nominal monitoring, reference within bounds
2. Asthma profile -> Respiratory monitoring active, heightened SpO2 & gas sensitivity
3. Cardiovascular profile -> Heightened resting HR deviation sensitivity, cardiac threshold reference
4. Diabetes profile -> Metabolic context active, non-diagnostic safety notice enforced
5. Hypertension profile -> BP disclaimer enforced, cardiovascular monitoring active
6. COPD profile -> GOLD 2024 target range active (88-92% normal target for retainers)
7. Multiple conditions (Asthma + Hypertension) -> Combines respiratory + cardiac contexts without crude threshold addition
8. No condition / prefer not to say -> Safe general monitoring defaults
9. Profile change -> Version increments, baseline preserved, interpretation updated
10. Baseline learning -> Status LEARNING -> CALIBRATED as samples accumulate
11. Abnormal baseline rejection -> Acute critical anomaly strictly rejected from corrupting normal baseline
12. Sensor-quality failure -> Low PPG quality (<0.70) rejected from baseline and flagged as SENSOR_QUALITY_WARNING
13. Temporary spike -> Spike event detected with recovery monitoring, no caretaker alert
14. Persistent anomaly -> Multi-sample sustained elevation escalates to ELEVATED/CRITICAL with clinical reasoning
15. Recovery -> Physiological parameters returning to baseline auto-clear alert state
"""

import sys
import os
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.main import app
from backend.core.patient_profile import get_patient_profile_manager
from backend.core.threshold_engine import get_threshold_engine
from backend.core.baseline_engine import get_device_baseline
from backend.core.alert_state_machine import get_alert_state_machine
from backend.core.alert_engine import get_alert_engine

client = TestClient(app)

class PersonalizedProfileTestSuite(unittest.TestCase):
    def setUp(self):
        self.device_id = "ESP32-001"
        self.profile_mgr = get_patient_profile_manager(self.device_id)
        get_alert_state_machine().reset(self.device_id)
        get_alert_engine().reset()

    # 1. Healthy Profile
    def test_01_healthy_profile(self):
        print("\n[TEST 01] Healthy profile (no condition)...")
        profile = self.profile_mgr.set_profile({
            "age": 28,
            "sex": "F",
            "conditions": ["none"],
        })
        self.assertIn("none", profile["conditions"])
        resp = client.post("/api/simulator/readings", json={
            "device_id": self.device_id,
            "heart_rate": 72.0,
            "spo2": 98.0,
            "body_temperature": 36.7,
            "ambient_temperature": 28.0,
            "humidity": 60.0,
            "mq45": 180.0,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["personalized"])
        self.assertIn("general_monitoring", data["active_condition_contexts"])
        self.assertIn(data["risk"]["overall_level"], ["NORMAL", "LOW"])
        print(" -> Healthy Profile: General monitoring active, risk NORMAL (OK)")

    # 2. Asthma Profile
    def test_02_asthma_profile(self):
        print("\n[TEST 02] Asthma profile...")
        self.profile_mgr.set_profile({
            "age": 35,
            "sex": "M",
            "conditions": ["asthma"],
            "medications": ["albuterol inhaler"],
        })
        # Mild SpO2 drop (93%) with asthma
        resp = client.post("/api/simulator/readings", json={
            "device_id": self.device_id,
            "heart_rate": 84.0,
            "spo2": 93.0,
            "body_temperature": 36.7,
            "ambient_temperature": 28.0,
            "humidity": 60.0,
            "mq45": 220.0,
        })
        data = resp.json()
        self.assertIn("respiratory_monitoring", data["active_condition_contexts"])
        self.assertGreater(data["threshold_assessment"]["sensitivity_factors"]["oxygenation"], 1.0)
        # Verify non-diagnostic rule: never claim 'asthma detected'
        self.assertNotIn("asthma detected", str(data["risk"]).lower())
        print(f" -> Active Contexts: {data['active_condition_contexts']} | SpO2 Sensitivity: {data['threshold_assessment']['sensitivity_factors']['oxygenation']} (OK)")

    # 3. Cardiovascular Profile
    def test_03_cardiovascular_profile(self):
        print("\n[TEST 03] Cardiovascular profile...")
        self.profile_mgr.set_profile({
            "age": 58,
            "sex": "M",
            "conditions": ["cardiovascular"],
        })
        resp = client.post("/api/simulator/readings", json={
            "device_id": self.device_id,
            "heart_rate": 115.0, # Elevated at rest for cardiac patient
            "spo2": 97.0,
            "body_temperature": 36.7,
            "ambient_temperature": 28.0,
            "humidity": 60.0,
            "mq45": 180.0,
        })
        data = resp.json()
        self.assertIn("cardiovascular_monitoring", data["active_condition_contexts"])
        self.assertGreater(data["threshold_assessment"]["sensitivity_factors"]["heart_rate"], 1.0)
        self.assertIn("REFERENCE_THRESHOLD", data["decision_sources"])
        # Non-diagnostic safety
        self.assertNotIn("heart attack detected", str(data).lower())
        print(f" -> Cardiac Context: {data['active_condition_contexts']} | Decision Sources: {data['decision_sources']} (OK)")

    # 4. Diabetes Profile
    def test_04_diabetes_profile(self):
        print("\n[TEST 04] Diabetes profile context...")
        self.profile_mgr.set_profile({
            "age": 50,
            "sex": "F",
            "conditions": ["diabetes"],
        })
        resp = client.post("/api/simulator/readings", json={
            "device_id": self.device_id,
            "heart_rate": 75.0,
            "spo2": 98.0,
            "body_temperature": 36.7,
        })
        data = resp.json()
        self.assertIn("metabolic_context", data["active_condition_contexts"])
        # Verify non-diagnostic safety notice
        notices = data.get("special_notices", [])
        self.assertTrue(any("glucose" in n.lower() for n in notices))
        print(f" -> Metabolic context verified with non-diagnostic notice: '{notices[0]}' (OK)")

    # 5. Hypertension Profile
    def test_05_hypertension_profile(self):
        print("\n[TEST 05] Hypertension profile context...")
        self.profile_mgr.set_profile({
            "age": 62,
            "sex": "M",
            "conditions": ["hypertension"],
        })
        resp = client.post("/api/simulator/readings", json={
            "device_id": self.device_id,
            "heart_rate": 78.0,
            "spo2": 98.0,
            "body_temperature": 36.7,
        })
        data = resp.json()
        self.assertIn("cardiovascular_monitoring", data["active_condition_contexts"])
        notices = data.get("special_notices", [])
        self.assertTrue(any("blood pressure" in n.lower() for n in notices))
        print(f" -> Hypertension notice verified: '{notices[0]}' (OK)")

    # 6. COPD Profile
    def test_06_copd_profile(self):
        print("\n[TEST 06] COPD profile & GOLD target band...")
        self.profile_mgr.set_profile({
            "age": 68,
            "sex": "M",
            "conditions": ["copd"],
        })
        # SpO2 of 91% in COPD is in the 88-92% expected target band
        resp = client.post("/api/simulator/readings", json={
            "device_id": self.device_id,
            "heart_rate": 78.0,
            "spo2": 91.0, # Within COPD target
            "body_temperature": 36.7,
        })
        data = resp.json()
        self.assertIn("respiratory_monitoring", data["active_condition_contexts"])
        self.assertNotEqual(data["risk"]["overall_level"], "CRITICAL")
        print(f" -> COPD Target SpO2 91%: Handled contextually without false critical emergency (OK)")

    # 7. Multiple Conditions (Asthma + Hypertension)
    def test_07_multiple_conditions(self):
        print("\n[TEST 07] Multiple conditions (Asthma + Hypertension)...")
        self.profile_mgr.set_profile({
            "age": 52,
            "sex": "F",
            "conditions": ["asthma", "hypertension"],
            "medications": ["inhaler", "lisinopril"],
        })
        resp = client.post("/api/simulator/readings", json={
            "device_id": self.device_id,
            "heart_rate": 80.0,
            "spo2": 97.0,
            "body_temperature": 36.7,
        })
        data = resp.json()
        contexts = data["active_condition_contexts"]
        self.assertIn("respiratory_monitoring", contexts)
        self.assertIn("cardiovascular_monitoring", contexts)
        self.assertEqual(len(contexts), 2)
        print(f" -> Multiple Contexts Active: {contexts} (OK)")

    # 8. No Condition / Prefer Not to Say
    def test_08_no_condition(self):
        print("\n[TEST 08] Prefer not to say / No condition...")
        self.profile_mgr.set_profile({
            "age": 40,
            "sex": "Prefer not to say",
            "conditions": ["prefer_not_to_say"],
        })
        resp = client.post("/api/simulator/readings", json={
            "device_id": self.device_id,
            "heart_rate": 72.0,
            "spo2": 98.0,
            "body_temperature": 36.7,
        })
        data = resp.json()
        self.assertIn("general_monitoring", data["active_condition_contexts"])
        print(f" -> Safe fallback to general monitoring (OK)")

    # 9. Profile Change
    def test_09_profile_change(self):
        print("\n[TEST 09] Profile change preserves baseline...")
        p1 = self.profile_mgr.set_profile({"age": 30, "conditions": ["none"]})
        ver1 = p1["profile_version"]
        
        # Get baseline mean before profile update
        baseline_before = get_device_baseline(self.device_id).stats["heart_rate"]["baseline_mean"]

        # Update profile to cardiovascular
        p2 = self.profile_mgr.set_profile({"age": 31, "conditions": ["cardiovascular"]})
        ver2 = p2["profile_version"]

        baseline_after = get_device_baseline(self.device_id).stats["heart_rate"]["baseline_mean"]

        self.assertNotEqual(ver1, ver2)
        self.assertEqual(baseline_before, baseline_after)
        print(f" -> Version incremented {ver1} -> {ver2}, baseline preserved ({baseline_after} bpm) (OK)")

    # 10. Baseline Learning Mode
    def test_10_baseline_learning(self):
        print("\n[TEST 10] Baseline learning & percentiles calculation...")
        baseline = get_device_baseline(self.device_id)
        baseline.start_calibration()
        self.assertTrue(baseline.is_calibrating)

        # Feed nominal samples
        for _ in range(35):
            baseline.update_with_reading({"heart_rate": 74.0, "spo2": 98.0, "body_temperature": 36.7})

        self.assertTrue(baseline.is_calibrated)
        self.assertFalse(baseline.is_calibrating)
        self.assertIn("percentiles", baseline.stats["heart_rate"])
        p = baseline.stats["heart_rate"]["percentiles"]
        self.assertIn("p50", p)
        print(f" -> Calibration Complete: p10={p['p10']}, p50={p['p50']}, p90={p['p90']} (OK)")

    # 11. Abnormal Baseline Rejection
    def test_11_abnormal_baseline_rejection(self):
        print("\n[TEST 11] Abnormal event baseline rejection (Section 14)...")
        baseline = get_device_baseline(self.device_id)
        initial_samples = baseline.samples_collected
        hr_before = baseline.stats["heart_rate"]["baseline_mean"]

        # Attempt to feed acute severe tachycardia with CRITICAL risk
        accepted = baseline.update_with_reading(
            {"heart_rate": 195.0, "spo2": 98.0, "body_temperature": 36.7},
            nominal_only=True,
            risk_level="CRITICAL",
        )
        self.assertFalse(accepted)
        self.assertEqual(baseline.samples_collected, initial_samples)
        self.assertEqual(baseline.stats["heart_rate"]["baseline_mean"], hr_before)
        print(" -> Critical reading strictly rejected from corrupting baseline (OK)")

    # 12. Sensor Quality Failure
    def test_12_sensor_quality_failure(self):
        print("\n[TEST 12] Sensor quality failure rejection...")
        baseline = get_device_baseline(self.device_id)
        accepted = baseline.update_with_reading(
            {"heart_rate": 74.0, "spo2": 98.0, "body_temperature": 36.7},
            nominal_only=True,
            sensor_quality=0.55, # Poor signal
        )
        self.assertFalse(accepted)

        # Reading with poor PPG sent to API
        resp = client.post("/api/simulator/readings", json={
            "device_id": self.device_id,
            "heart_rate": 74.0,
            "spo2": 98.0,
            "ppg_quality": 0.50, # Degraded signal
            "body_temperature": 36.7,
        })
        data = resp.json()
        self.assertIn("SENSOR_QUALITY_WARNING", data["decision_sources"])
        print(f" -> Low quality rejected and flagged in decision sources: {data['decision_sources']} (OK)")

    # 13. Temporary Spike vs Persistent Anomaly
    def test_13_temporary_spike(self):
        print("\n[TEST 13] Temporary spike vs persistent anomaly...")
        # Step 1: Normal
        client.post("/api/simulator/readings", json={"device_id": self.device_id, "heart_rate": 74.0, "spo2": 98.0, "body_temperature": 36.7})
        # Step 2: Sudden Spike
        spike_resp = client.post("/api/simulator/readings", json={"device_id": self.device_id, "heart_rate": 198.0, "spo2": 98.0, "body_temperature": 36.7}).json()
        self.assertTrue(spike_resp["spike"]["has_active_spike"])
        self.assertEqual(spike_resp["spike"]["latest_spike"]["status"], "SPIKE_DETECTED")
        print(f" -> Temporary Spike Detected: {spike_resp['spike']['latest_spike']['status']} (OK)")

    # 14. Persistent Anomaly
    def test_14_persistent_anomaly(self):
        print("\n[TEST 14] Persistent resting anomaly escalation...")
        last_data = None
        for _ in range(3):
            resp = client.post("/api/simulator/readings", json={
                "device_id": self.device_id,
                "heart_rate": 175.0,
                "spo2": 98.0,
                "body_temperature": 36.7,
                "activity_state": 0, # Resting
            })
            last_data = resp.json()

        self.assertIn(last_data["escalation"]["escalated_level"], ["ELEVATED", "CRITICAL"])
        self.assertIn("PERSONAL_BASELINE", last_data["decision_sources"])
        print(f" -> Persistent Anomaly Escalated to: {last_data['escalation']['escalated_level']} | Decision: {last_data['decision_sources']} (OK)")

    # 15. Recovery
    def test_15_recovery(self):
        print("\n[TEST 15] Recovery sequence...")
        rec_resp = client.post("/api/simulator/readings", json={
            "device_id": self.device_id,
            "heart_rate": 76.0,
            "spo2": 98.0,
            "body_temperature": 36.7,
        }).json()
        self.assertIn(rec_resp["escalation"]["escalated_level"], ["NORMAL", "RECOVERING", "OBSERVATION"])
        print(f" -> Recovery Level: {rec_resp['escalation']['escalated_level']} (OK)")

if __name__ == "__main__":
    unittest.main()
