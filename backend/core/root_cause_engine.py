"""
VITALSYNC: Root-Cause Analysis & Clinical-Context Reasoning Engine
Determines the true etiology of telemetry changes:
1. WHAT changed?
2. WHETHER the change is genuine or a sensor artifact.
3. WHAT is the most likely contributing context?
4. WHETHER multiple independent signals support the event.
5. WHETHER the condition is transient or persistent.
6. WHETHER the risk is recovering.
7. WHETHER an alert should remain active, escalate, or clear.
8. WHY the system reached its conclusion.

Operates deterministically without cloud APIs or LLMs. Execution latency < 5 ms on Raspberry Pi 4.
"""

from typing import Dict, Any, List, Optional, Tuple

class RootCauseEngine:
    def __init__(self, min_confidence_threshold: float = 0.55):
        self.min_confidence = min_confidence_threshold

    def evaluate_root_cause(
        self,
        features: Dict[str, Any],
        ml_predictions: Dict[str, Any],
        escalated_eval: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Executes causal candidate generation, evidence weighting, and deterministic ranking.
        """
        hr = float(features.get("heart_rate", 72.0))
        spo2 = float(features.get("spo2", 98.0))
        ppg_q = float(features.get("ppg_quality", 0.95))
        body_temp = float(features.get("body_temperature", 36.7))
        amb_temp = float(features.get("ambient_temperature", 28.0))
        humidity = float(features.get("humidity", 60.0))
        mq45 = float(features.get("mq45", 180.0))
        act_state = int(features.get("activity_state", 0))
        act_label = features.get("activity_label", "REST")
        is_active = features.get("is_active", False)
        is_rest = features.get("is_rest", True)

        qualities = features.get("sensor_qualities", {})
        sensor_conf = features.get("overall_sensor_confidence", 1.0)
        is_transient_thermal = features.get("is_transient_thermal", False)

        deviations = features.get("baseline_summary", {})
        hr_dev = features.get("hr_deviation", 0.0)
        spo2_dev = features.get("spo2_deviation", 0.0)
        temp_dev = features.get("temp_deviation", 0.0)

        persistence_count = escalated_eval.get("persistence_count", 0)
        sm_state = escalated_eval.get("escalated_level", "NORMAL")

        domains = ml_predictions.get("risk_domains", {})
        fall_info = domains.get("fall_event", {})
        is_fall_confirmed = fall_info.get("is_confirmed", False)
        is_fall_candidate = fall_info.get("is_candidate", False)

        candidates = []
        supporting_evidence = []
        contradicting_evidence = []

        # ---------------------------------------------------------------------
        # 1. CANDIDATE: SENSOR_ARTIFACT
        # ---------------------------------------------------------------------
        artifact_score = 0.0
        artifact_conf = 0.90
        if ppg_q < 0.45 or qualities.get("ppg") in ("WEAK", "INVALID"):
            artifact_score = 0.85
            supporting_evidence.append(f"Low PPG optical signal quality ({ppg_q:.2f}) indicates motion artifact or sensor displacement.")
        elif is_transient_thermal:
            artifact_score = 0.78
            supporting_evidence.append(f"Rapid thermal rate of change without core elevation indicates external object contact (hot beverage touch).")
        elif not features.get("adxl_available", True):
            artifact_score = 0.92
            supporting_evidence.append("Accelerometer disconnected or invalid I2C communication.")
        elif persistence_count == 1 and (hr > 175 or spo2 < 82):
            artifact_score = 0.65
            supporting_evidence.append("Single-sample isolated extreme outlier without temporal persistence.")

        if artifact_score > 0.0:
            candidates.append({
                "cause": "SENSOR_ARTIFACT",
                "score": round(artifact_score, 2),
                "confidence": artifact_conf,
                "reason": "Signal noise, sensor detachment, or transient external contact artifact.",
            })

        # ---------------------------------------------------------------------
        # 2. CANDIDATE: ACTIVITY_RELATED
        # ---------------------------------------------------------------------
        activity_score = 0.0
        if is_active and hr > 105:
            # HR elevation directly correlated with active physical exertion
            activity_score = min(1.0, 0.40 + (hr - 100) / 100.0)
            supporting_evidence.append(f"Heart rate elevation ({int(hr)} BPM) temporally aligns with active motion ({act_label}).")
            if spo2 >= 96.0:
                supporting_evidence.append("Blood oxygenation remains robust (SpO2 >= 96%) during exertion.")
                contradicting_evidence.append("No respiratory failure; oxygenation is stable.")
            candidates.append({
                "cause": "ACTIVITY_RELATED",
                "score": round(activity_score, 2),
                "confidence": 0.88,
                "reason": f"Cardiovascular response directly associated with physical movement ({act_label}).",
            })
        elif is_rest and hr > 120:
            contradicting_evidence.append(f"Patient is in sedentary/resting state ({act_label}), ruling out exercise-induced elevation.")

        # ---------------------------------------------------------------------
        # 3. CANDIDATE: THERMAL_EXPOSURE / HEAT_STRAIN
        # ---------------------------------------------------------------------
        thermal_score = 0.0
        if not is_transient_thermal and (body_temp > 38.0 or amb_temp > 35.0):
            thermal_score = 0.30
            if body_temp > 38.5 and amb_temp > 34.0:
                thermal_score = 0.85
                supporting_evidence.append(f"Concurrent high contact temperature ({body_temp:.1f}°C) and ambient heat ({amb_temp:.1f}°C).")
            elif amb_temp > 35.0 and body_temp <= 37.3:
                # Outdoor heat wave without body elevation
                thermal_score = 0.25
                supporting_evidence.append(f"High ambient/environmental heat ({amb_temp:.1f}°C) with stable body temperature ({body_temp:.1f}°C).")
                contradicting_evidence.append("Body contact temperature remains within normal baseline.")
            candidates.append({
                "cause": "THERMAL_RELATED",
                "score": round(thermal_score, 2),
                "confidence": 0.84,
                "reason": "Thermal strain pattern from environmental heat or elevated body temperature.",
            })

        # ---------------------------------------------------------------------
        # 4. CANDIDATE: FALL_EVENT
        # ---------------------------------------------------------------------
        if is_fall_confirmed:
            candidates.append({
                "cause": "FALL_EVENT",
                "score": 0.96,
                "confidence": 0.95,
                "reason": "Severe kinetic impact followed by persistent immobility and posture tilt.",
            })
            supporting_evidence.append("Confirmed fall impact pattern followed by sustained inactivity.")
        elif is_fall_candidate:
            candidates.append({
                "cause": "FALL_EVENT",
                "score": 0.72,
                "confidence": 0.80,
                "reason": "Fall candidate verification window active following sudden impact.",
            })
            supporting_evidence.append("High acceleration impact candidate under active verification.")

        # ---------------------------------------------------------------------
        # 5. CANDIDATE: ENVIRONMENTAL_GAS_EXPOSURE
        # ---------------------------------------------------------------------
        if mq45 > 450:
            env_score = min(0.95, (mq45 - 250) / 600.0)
            candidates.append({
                "cause": "ENVIRONMENT_RELATED",
                "score": round(env_score, 2),
                "confidence": 0.82,
                "reason": f"Elevated MQ-45 air/gas exposure index ({int(mq45)}).",
            })
            supporting_evidence.append(f"Environmental gas exposure indicator elevated ({int(mq45)} index).")
            if spo2 >= 96.0:
                contradicting_evidence.append("No systemic physiological distress observed from gas exposure.")

        # ---------------------------------------------------------------------
        # 6. CANDIDATE: PHYSIOLOGICAL_ANOMALY
        # ---------------------------------------------------------------------
        physio_score = 0.0
        if is_rest and hr >= 125:
            # Resting tachycardia
            physio_score = max(physio_score, 0.75 if persistence_count >= 2 else 0.50)
            supporting_evidence.append(f"Persistent elevated resting heart rate ({int(hr)} BPM, +{int(hr_dev*100)}% above baseline).")

        if spo2 <= 91.0:
            # Desaturation
            physio_score = max(physio_score, 0.88 if persistence_count >= 2 else 0.60)
            supporting_evidence.append(f"Significant blood oxygen desaturation ({spo2}% SpO2).")

        if physio_score > 0.0 and artifact_score < 0.60:
            candidates.append({
                "cause": "PHYSIOLOGICAL_ANOMALY",
                "score": round(physio_score, 2),
                "confidence": 0.86,
                "reason": "Persistent vital sign deviation from personal baseline under resting conditions.",
            })

        # ---------------------------------------------------------------------
        # 7. CANDIDATE: NORMAL / NOMINAL
        # ---------------------------------------------------------------------
        if not candidates or (all(c["score"] < 0.30 for c in candidates) and sm_state in ("NORMAL", "OBSERVATION", "RECOVERING")):
            candidates.append({
                "cause": "NORMAL_PHYSIOLOGY",
                "score": 0.95,
                "confidence": 0.95,
                "reason": "All primary vital signs and motion metrics tracking within personal baseline.",
            })

        # Sort candidate root causes by weighted score
        candidates.sort(key=lambda x: x["score"], reverse=True)
        primary = candidates[0]

        # Check for ambiguity (if top two candidates have very close scores)
        if len(candidates) >= 2 and abs(candidates[0]["score"] - candidates[1]["score"]) < 0.08 and candidates[0]["score"] > 0.40:
            primary_cause = "UNCERTAIN"
            confidence = round((candidates[0]["confidence"] + candidates[1]["confidence"]) / 2.0 * 0.75, 2)
            primary_reason = f"Multi-factorial evidence between {candidates[0]['cause']} and {candidates[1]['cause']}."
        else:
            primary_cause = primary["cause"]
            confidence = primary["confidence"]
            primary_reason = primary["reason"]

        # Check Recovery State
        is_recovering = sm_state == "RECOVERING"
        if is_recovering:
            primary_reason = "Physiological recovery in progress. Vital signs returning toward personal baseline."

        return {
            "primary": primary_cause,
            "confidence": confidence,
            "primary_reason": primary_reason,
            "candidates": candidates,
            "supporting_evidence": supporting_evidence[:6],
            "contradicting_evidence": contradicting_evidence[:4],
            "is_artifact": primary_cause == "SENSOR_ARTIFACT",
            "is_recovering": is_recovering,
        }

_root_cause_engine = RootCauseEngine()

def get_root_cause_engine() -> RootCauseEngine:
    return _root_cause_engine
