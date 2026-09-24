"""
VITALSYNC: Multimodal ML Model Registry & Contextual Inference Engine
Executes unified edge inference across 8 decoupled risk domains:
1. Heart Rate Anomaly (XGBoost)
2. Oxygenation Anomaly (XGBoost)
3. Respiratory Risk (XGBoost - multi-signal gated)
4. Heat-Stress & Thermal Strain Risk (XGBoost + NTC contact filter)
5. Environmental Exposure (XGBoost MQ-45 Index)
6. Activity Strain (XGBoost)
7. Fall & Immobility Event (Dedicated Temporal State Engine)
8. General Physiological Anomaly (XGBoost / IsolationForest)

Adheres strictly to explainable, non-diagnostic medical framing.
"""

import os
import sys
import json
import joblib
import datetime
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.ml.tiny_tcn import get_tiny_tcn_engine
from backend.core.fall_engine import get_fall_engine

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

LEVEL_MAP = {
    0: "LOW",
    1: "EARLY_WARNING",
    2: "ELEVATED",
    3: "CRITICAL",
}

DOMAINS = [
    "heart_rate_anomaly",
    "oxygenation_anomaly",
    "respiratory_risk",
    "heat_stress_risk",
    "environmental_risk",
    "activity_strain",
    "general_anomaly",
]

class ModelRegistry:
    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.scalers: Dict[str, Any] = {}
        self.features: Dict[str, List[str]] = {}
        self.isoforest = None
        self.version_info: Dict[str, Any] = {}
        self.loaded = False
        self.tcn = get_tiny_tcn_engine()
        self.fall_engine = get_fall_engine()
        self._load_artifacts()

    def _load_artifacts(self):
        try:
            for domain in DOMAINS:
                model_file = os.path.join(MODELS_DIR, f"{domain}_model.joblib")
                scaler_file = os.path.join(MODELS_DIR, f"{domain}_scaler.joblib")
                feat_file = os.path.join(MODELS_DIR, f"{domain}_features.json")

                if os.path.exists(model_file):
                    self.models[domain] = joblib.load(model_file)
                    self.scalers[domain] = joblib.load(scaler_file)
                    with open(feat_file) as f:
                        self.features[domain] = json.load(f)

            iso_file = os.path.join(MODELS_DIR, "general_anomaly_isoforest.joblib")
            if os.path.exists(iso_file):
                self.isoforest = joblib.load(iso_file)

            version_file = os.path.join(MODELS_DIR, "model_version.json")
            if os.path.exists(version_file):
                with open(version_file) as f:
                    self.version_info = json.load(f)

            self.loaded = len(self.models) >= 5
            print(f"[ModelRegistry] Loaded {len(self.models)} decoupled ML models. Edge-AI suite ready.")
        except Exception as e:
            print(f"[ModelRegistry] Artifact load warning: {e}. Fallback heuristics active.")
            self.loaded = False

    def _predict_domain(self, domain: str, features: Dict[str, Any]) -> Dict[str, Any]:
        """Runs inference for a specific domain model and returns score, level, confidence, and reasoning."""
        if not self.loaded or domain not in self.models:
            return self._fallback_domain(domain, features)

        cols = self.features[domain]
        row = [float(features.get(c, 0.0)) for c in cols]
        vec = pd.DataFrame([row], columns=cols)
        vec_scaled = self.scalers[domain].transform(vec)

        pred_class = int(self.models[domain].predict(vec_scaled)[0])
        pred_probs = self.models[domain].predict_proba(vec_scaled)[0]
        confidence = float(np.max(pred_probs))

        # Continuous risk score mapping
        score = float(np.sum(pred_probs * np.array([0.08, 0.35, 0.72, 1.0][:len(pred_probs)])))
        level = LEVEL_MAP.get(pred_class, "LOW")

        return {
            "score": round(score, 3),
            "level": level,
            "confidence": round(confidence, 3),
            "pred_class": pred_class,
        }

    def _fallback_domain(self, domain: str, features: Dict[str, Any]) -> Dict[str, Any]:
        """Safety rule-based fallback if model binary is missing."""
        hr = features.get("heart_rate", 72)
        spo2 = features.get("spo2", 98)
        act = features.get("activity_state", 0)

        if domain == "heart_rate_anomaly":
            if act in (0, 1) and (hr > 160 or hr < 45):
                return {"score": 0.85, "level": "CRITICAL", "confidence": 0.90}
            elif act in (0, 1) and hr > 125:
                return {"score": 0.68, "level": "ELEVATED", "confidence": 0.88}
            elif hr > 95:
                return {"score": 0.35, "level": "EARLY_WARNING", "confidence": 0.82}
            return {"score": 0.10, "level": "LOW", "confidence": 0.95}

        if domain == "oxygenation_anomaly":
            if spo2 < 88:
                return {"score": 0.88, "level": "CRITICAL", "confidence": 0.95}
            elif spo2 < 93:
                return {"score": 0.65, "level": "ELEVATED", "confidence": 0.90}
            return {"score": 0.08, "level": "LOW", "confidence": 0.95}

        return {"score": 0.10, "level": "LOW", "confidence": 0.90}

    def predict_all(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes complete multimodal risk fusion across all 8 decoupled domains.
        Returns clean, domain-separated risk contract.
        """
        device_id = features.get("device_id", "ESP32-001")
        hr = float(features.get("heart_rate", 72.0))
        spo2 = float(features.get("spo2", 98.0))
        body_temp = float(features.get("body_temperature", 36.7))
        amb_temp = float(features.get("ambient_temperature", 28.0))
        humidity = float(features.get("humidity", 60.0))
        mq45 = float(features.get("mq45", 180.0))
        act_state = int(features.get("activity_state", 0))
        act_label = features.get("activity_label", "REST")
        
        # Sensor quality weighting
        qualities = features.get("sensor_qualities", {})
        sensor_conf = features.get("overall_sensor_confidence", 1.0)
        
        # 1. Heart Rate Anomaly
        hr_res = self._predict_domain("heart_rate_anomaly", features)
        hr_dev = features.get("hr_deviation", 0.0)
        is_exercise = act_state in (3, 4)
        
        # Contextual refinement for Heart Rate:
        # If exercise/high activity, HR elevation is expected physiological response!
        if is_exercise and hr < 165 and spo2 >= 96:
            hr_res["score"] = min(hr_res["score"], 0.28)
            hr_res["level"] = "LOW"
            hr_reason = f"Normal cardiovascular response to exercise ({int(hr)} BPM during {act_label})."
        elif hr >= 160 and act_state in (0, 1):
            hr_res["level"] = "CRITICAL" if hr >= 180 else "ELEVATED"
            hr_res["score"] = max(hr_res["score"], 0.82)
            hr_reason = f"Severe resting tachycardia ({int(hr)} BPM, +{int(hr_dev*100)}% above resting baseline)."
        elif hr >= 120 and act_state in (0, 1):
            hr_res["level"] = "ELEVATED"
            hr_res["score"] = max(hr_res["score"], 0.65)
            hr_reason = f"Elevated resting heart rate ({int(hr)} BPM at rest)."
        elif hr > 95:
            hr_reason = f"Mild heart rate elevation ({int(hr)} BPM)."
        else:
            hr_reason = f"Heart rate normal ({int(hr)} BPM, within baseline)."

        # 2. Oxygenation Anomaly
        spo2_res = self._predict_domain("oxygenation_anomaly", features)
        if spo2 <= 85:
            spo2_reason = f"Severe blood oxygen desaturation ({spo2}%)."
        elif spo2 <= 91:
            spo2_reason = f"Elevated oxygenation anomaly ({spo2}%)."
        elif spo2 <= 95:
            spo2_reason = f"Mild oxygenation drop ({spo2}%)."
        else:
            spo2_reason = f"Oxygen saturation optimal ({spo2}%)."

        # 3. Respiratory Risk (CRUCIAL: Requires multimodal respiratory evidence!)
        resp_res = self._predict_domain("respiratory_risk", features)
        # Rule: If SpO2 is completely normal (>= 96%) and MQ-45 is normal, NEVER label as respiratory distress!
        if spo2 >= 96.0 and mq45 < 400:
            resp_res["score"] = min(resp_res["score"], 0.12)
            resp_res["level"] = "LOW"
            resp_reason = "No respiratory distress evidence. Oxygenation stable."
        elif spo2 <= 88:
            resp_reason = f"Elevated respiratory risk: concurrent hypoxemia ({spo2}%) and cardiac compensation."
        elif spo2 <= 93 and hr > 100:
            resp_reason = f"Respiratory strain: desaturation ({spo2}%) with elevated heart rate."
        else:
            resp_reason = "Respiratory parameters tracking normally."

        # 4. Heat Stress & Thermal Strain (Includes NTC contact disturbance filter!)
        heat_res = self._predict_domain("heat_stress_risk", features)
        is_transient_thermal = features.get("is_transient_thermal", False)
        if is_transient_thermal:
            # Hot beverage contact touch detected! Dampen thermal risk score
            heat_res["score"] = 0.15
            heat_res["level"] = "LOW"
            heat_reason = f"Transient external contact spike ({body_temp:.1f}°C). Rapid cooling observed, no systemic heat stress."
        elif amb_temp < 25.0 and body_temp < 37.2:
            heat_res["score"] = 0.08
            heat_res["level"] = "LOW"
            heat_reason = f"Normal thermal regulation in cool/temperate environment ({amb_temp:.1f}°C)."
        elif body_temp > 38.8 and amb_temp > 34.0:
            heat_res["level"] = "CRITICAL"
            heat_res["score"] = max(heat_res["score"], 0.85)
            heat_reason = f"Severe thermal strain: high body temp ({body_temp:.1f}°C) and ambient heat ({amb_temp:.1f}°C)."
        elif body_temp > 37.8:
            heat_reason = f"Elevated body temperature ({body_temp:.1f}°C)."
        else:
            heat_reason = f"Thermal equilibrium maintained ({body_temp:.1f}°C contact, {amb_temp:.1f}°C ambient)."

        # 5. Environmental Gas Exposure
        env_res = self._predict_domain("environmental_risk", features)
        if mq45 > 650:
            env_reason = f"Elevated air/gas exposure indicator ({int(mq45)} index). Non-diagnostic environmental advisory."
        elif mq45 > 350:
            env_reason = f"Moderate ambient environmental exposure ({int(mq45)} index)."
        else:
            env_reason = f"Environmental air quality index nominal ({int(mq45)})."

        # 6. Activity Strain
        act_res = self._predict_domain("activity_strain", features)
        act_reason = f"Activity level: {act_label} (Intensity {features.get('activity_intensity', 'NORMAL')})."

        # 7. Fall & Immobility Event (From dedicated temporal FallEngine)
        fall_eval = self.fall_engine.evaluate(
            device_id=device_id,
            ax=features.get("accel_x", 0.0),
            ay=features.get("accel_y", 0.0),
            az=features.get("accel_z", 0.98),
            sensor_valid=features.get("adxl_available", True),
        )
        if fall_eval["is_candidate"]:
            features["fall_candidate"] = True
            features["is_fall_candidate"] = True
            features["activity_level"] = "FALL_CANDIDATE"
            features["activity_label"] = "FALL_CANDIDATE"

        # 8. General Anomaly
        gen_res = self._predict_domain("general_anomaly", features)

        # Build Domain Map
        domains = {
            "heart_rate_anomaly": {
                "name": "Heart Rate Anomaly",
                "score": hr_res["score"],
                "level": hr_res["level"],
                "risk_level": hr_res["level"],
                "confidence": hr_res["confidence"],
                "reason": hr_reason,
                "contributing_features": ["heart_rate", "hr_deviation", "activity_state"],
            },
            "oxygenation_anomaly": {
                "name": "Oxygenation Anomaly",
                "score": spo2_res["score"],
                "level": spo2_res["level"],
                "risk_level": spo2_res["level"],
                "confidence": spo2_res["confidence"],
                "reason": spo2_reason,
                "contributing_features": ["spo2", "spo2_deviation"],
            },
            "respiratory_risk": {
                "name": "Respiratory Risk",
                "score": resp_res["score"],
                "level": resp_res["level"],
                "risk_level": resp_res["level"],
                "confidence": resp_res["confidence"],
                "reason": resp_reason,
                "contributing_features": ["spo2", "heart_rate", "mq45"],
            },
            "heat_stress_risk": {
                "name": "Heat / Thermal Strain",
                "score": heat_res["score"],
                "level": heat_res["level"],
                "risk_level": heat_res["level"],
                "confidence": heat_res["confidence"],
                "reason": heat_reason,
                "contributing_features": ["body_temperature", "ambient_temperature", "humidity", "heat_index"],
            },
            "environmental_exposure": {
                "name": "Environmental Exposure",
                "score": env_res["score"],
                "level": env_res["level"],
                "risk_level": env_res["level"],
                "confidence": env_res["confidence"],
                "reason": env_reason,
                "contributing_features": ["mq45", "ambient_temperature", "gas_exposure"],
            },
            "activity_strain": {
                "name": "Activity Strain",
                "score": act_res["score"],
                "level": act_res["level"],
                "risk_level": act_res["level"],
                "confidence": act_res["confidence"],
                "reason": act_reason,
                "contributing_features": ["accel_mag", "activity_state"],
            },
            "fall_event": {
                "name": "Fall & Immobility Event",
                "state": fall_eval["fall_state"],
                "is_candidate": fall_eval["is_candidate"],
                "is_confirmed": fall_eval["is_confirmed"],
                "confidence": fall_eval["confidence"],
                "reason": fall_eval["message"],
                "contributing_features": ["accel_mag", "horizontal_tilt", "inactivity"],
            },
            "general_anomaly": {
                "name": "General Physiological Anomaly",
                "score": gen_res["score"],
                "level": gen_res["level"],
                "risk_level": gen_res["level"],
                "confidence": gen_res["confidence"],
                "reason": "Multimodal physiological balance index.",
                "contributing_features": ["heart_rate", "spo2", "body_temperature"],
            },
        }

        # --- MULTIMODAL OVERALL RISK SYNTHESIS ---
        # Prioritized fusion: Never mask heart rate anomaly as respiratory distress!
        primary_domain = "General Physiological"
        primary_reason = "All signals tracking nominal."
        
        # Check Critical Fall Event First
        if fall_eval["is_confirmed"]:
            overall_score = 0.95
            overall_level = "CRITICAL"
            primary_domain = "Fall / Immobility Event"
            primary_reason = fall_eval["message"]
        elif fall_eval["is_candidate"]:
            overall_score = 0.70
            overall_level = "ELEVATED"
            primary_domain = "Fall Candidate"
            primary_reason = fall_eval["message"]
        else:
            # Find the highest genuine domain risk
            domain_ranking = [
                ("heart_rate_anomaly", hr_res["score"], hr_reason),
                ("oxygenation_anomaly", spo2_res["score"], spo2_reason),
                ("respiratory_risk", resp_res["score"], resp_reason),
                ("heat_stress_risk", heat_res["score"], heat_reason),
                ("environmental_exposure", env_res["score"] * 0.75, env_reason), # Environment is contextual
            ]
            domain_ranking.sort(key=lambda x: x[1], reverse=True)
            top_dom, top_score, top_reason = domain_ranking[0]

            # Contextual discount for sensor quality
            weighted_score = top_score * (0.5 + 0.5 * sensor_conf)

            if weighted_score >= 0.80:
                overall_level = "CRITICAL"
            elif weighted_score >= 0.65:
                overall_level = "ELEVATED"
            elif weighted_score >= 0.30:
                overall_level = "EARLY_WARNING"
            elif weighted_score >= 0.18:
                overall_level = "OBSERVATION"
            else:
                overall_level = "LOW"

            overall_score = weighted_score
            primary_domain = domains[top_dom]["name"] if top_score > 0.25 else "General Physiological"
            primary_reason = top_reason if top_score > 0.25 else "All signals tracking within personal baseline."

        # Supporting and contradicting features for explainability
        supporting = []
        contradicting = []

        if hr > 110:
            supporting.append(f"HR elevated ({int(hr)} BPM)")
        else:
            contradicting.append(f"HR normal ({int(hr)} BPM)")

        if spo2 < 94:
            supporting.append(f"SpO2 depressed ({spo2}%)")
        else:
            contradicting.append(f"SpO2 optimal ({spo2}%)")

        if is_exercise:
            contradicting.append("High physical activity explains elevated HR")

        if is_transient_thermal:
            contradicting.append("Fast thermal rate-of-change indicates contact disturbance, not fever")

        return {
            "overall_health_risk": {
                "score": round(overall_score, 3),
                "risk_level": overall_level,
                "level": overall_level,
                "primary_domain": primary_domain,
                "primary_reason": primary_reason,
                "confidence": round(sensor_conf, 2),
            },
            "risk_domains": domains,
            # Top-level aliases for backward compatibility
            "heart_rate_anomaly": domains["heart_rate_anomaly"],
            "oxygenation_anomaly": domains["oxygenation_anomaly"],
            "respiratory_risk": domains["respiratory_risk"],
            "heat_stress_risk": domains["heat_stress_risk"],
            "environmental_exposure_risk": domains["environmental_exposure"],
            "environmental_risk": domains["environmental_exposure"],
            "activity_strain": domains["activity_strain"],
            "fall_event": domains["fall_event"],
            "general_anomaly": domains["general_anomaly"],
            "explainability": {
                "primary_domain": primary_domain,
                "primary_reason": primary_reason,
                "supporting_features": supporting,
                "contradicting_features": contradicting,
                "sensor_quality_confidence": round(sensor_conf, 2),
            },
            "timestamp": features.get("timestamp", datetime.datetime.utcnow().isoformat() + "Z"),
        }

_registry: Optional[ModelRegistry] = None

def get_model_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
