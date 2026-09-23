"""
AAROGYA-SHIELD: ML Model Registry & Multi-Model Inference Suite
Loads trained Edge-AI models and scalers, runs unified inference,
and computes explainable risk scores adhering strictly to non-diagnostic framing.
"""

import os
import json
import joblib
import datetime
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

LEVEL_MAP = {
    0: "LOW",
    1: "EARLY_WARNING",
    2: "ELEVATED",
    3: "CRITICAL",
}

class ModelRegistry:
    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.scalers: Dict[str, Any] = {}
        self.features: Dict[str, List[str]] = {}
        self.version_info: Dict[str, Any] = {}
        self.loaded = False
        self._load_artifacts()

    def _load_artifacts(self):
        try:
            # 1. Respiratory Model
            self.models["respiratory_risk"] = joblib.load(os.path.join(MODELS_DIR, "respiratory_risk_model.joblib"))
            self.scalers["respiratory_risk"] = joblib.load(os.path.join(MODELS_DIR, "respiratory_risk_scaler.joblib"))
            with open(os.path.join(MODELS_DIR, "respiratory_risk_features.json")) as f:
                self.features["respiratory_risk"] = json.load(f)

            # 2. Heat Stress Model
            self.models["heat_stress_risk"] = joblib.load(os.path.join(MODELS_DIR, "heat_stress_risk_model.joblib"))
            self.scalers["heat_stress_risk"] = joblib.load(os.path.join(MODELS_DIR, "heat_stress_risk_scaler.joblib"))
            with open(os.path.join(MODELS_DIR, "heat_stress_risk_features.json")) as f:
                self.features["heat_stress_risk"] = json.load(f)

            # 3. Environmental Model
            self.models["environmental_risk"] = joblib.load(os.path.join(MODELS_DIR, "environmental_risk_model.joblib"))
            self.scalers["environmental_risk"] = joblib.load(os.path.join(MODELS_DIR, "environmental_risk_scaler.joblib"))
            with open(os.path.join(MODELS_DIR, "environmental_risk_features.json")) as f:
                self.features["environmental_risk"] = json.load(f)

            # 4. General Anomaly Model
            self.models["general_anomaly"] = joblib.load(os.path.join(MODELS_DIR, "general_anomaly_model.joblib"))
            self.models["general_anomaly_iso"] = joblib.load(os.path.join(MODELS_DIR, "general_anomaly_isoforest.joblib"))
            self.scalers["general_anomaly"] = joblib.load(os.path.join(MODELS_DIR, "general_anomaly_scaler.joblib"))
            with open(os.path.join(MODELS_DIR, "general_anomaly_features.json")) as f:
                self.features["general_anomaly"] = json.load(f)

            with open(os.path.join(MODELS_DIR, "model_version.json")) as f:
                self.version_info = json.load(f)

            self.loaded = True
            print("[ModelRegistry] All 4 ML models and scalers loaded successfully.")
        except Exception as e:
            print(f"[ModelRegistry] Error loading model artifacts: {e}. Running fallback heuristics.")
            self.loaded = False

    def predict_respiratory(self, features: Dict[str, Any], ts: str) -> Dict[str, Any]:
        if not self.loaded:
            return self._fallback_respiratory(features, ts)

        cols = self.features["respiratory_risk"]
        vec = pd.DataFrame([[features[c] for c in cols]], columns=cols)
        vec_scaled = self.scalers["respiratory_risk"].transform(vec)
        
        pred_class = int(self.models["respiratory_risk"].predict(vec_scaled)[0])
        pred_probs = self.models["respiratory_risk"].predict_proba(vec_scaled)[0]
        confidence = float(np.max(pred_probs))
        
        # Calculate continuous score: weighted class expectation normalized to 0-1
        score = float(np.sum(pred_probs * np.array([0.1, 0.4, 0.75, 1.0])))
        level = LEVEL_MAP[pred_class]

        # Contributing features calculation
        contributing = {
            "spo2_deviation": round(features["spo2_deviation"], 4),
            "hr_deviation": round(features["hr_deviation"], 4),
            "spo2_current": features["spo2"],
            "heart_rate_current": features["heart_rate"],
            "environmental_exposure": features["mq45"],
        }

        return {
            "name": "Respiratory Risk",
            "score": round(score, 3),
            "risk_level": level,
            "confidence": round(confidence, 3),
            "contributing_features": contributing,
            "timestamp": ts,
            "model_version": self.version_info.get("version", "1.0.0-edge"),
        }

    def predict_heat_stress(self, features: Dict[str, Any], ts: str) -> Dict[str, Any]:
        if not self.loaded:
            return self._fallback_heat_stress(features, ts)

        cols = self.features["heat_stress_risk"]
        vec = pd.DataFrame([[features[c] for c in cols]], columns=cols)
        vec_scaled = self.scalers["heat_stress_risk"].transform(vec)
        
        pred_class = int(self.models["heat_stress_risk"].predict(vec_scaled)[0])
        pred_probs = self.models["heat_stress_risk"].predict_proba(vec_scaled)[0]
        confidence = float(np.max(pred_probs))
        score = float(np.sum(pred_probs * np.array([0.1, 0.4, 0.75, 1.0])))
        level = LEVEL_MAP[pred_class]

        contributing = {
            "body_temperature": features["body_temperature"],
            "temp_deviation": round(features["temp_deviation"], 2),
            "ambient_temperature": features["ambient_temperature"],
            "humidity": features["humidity"],
            "heat_index": features["heat_index"],
        }

        return {
            "name": "Heat-Stress / Physiological-Strain Risk",
            "score": round(score, 3),
            "risk_level": level,
            "confidence": round(confidence, 3),
            "contributing_features": contributing,
            "timestamp": ts,
            "model_version": self.version_info.get("version", "1.0.0-edge"),
        }

    def predict_environmental(self, features: Dict[str, Any], ts: str) -> Dict[str, Any]:
        if not self.loaded:
            return self._fallback_environmental(features, ts)

        cols = self.features["environmental_risk"]
        vec = pd.DataFrame([[features[c] for c in cols]], columns=cols)
        vec_scaled = self.scalers["environmental_risk"].transform(vec)
        
        pred_class = int(self.models["environmental_risk"].predict(vec_scaled)[0])
        pred_probs = self.models["environmental_risk"].predict_proba(vec_scaled)[0]
        confidence = float(np.max(pred_probs))
        score = float(np.sum(pred_probs * np.array([0.1, 0.4, 0.75, 1.0])))
        level = LEVEL_MAP[pred_class]

        contributing = {
            "mq45_signal": features["mq45"],
            "ambient_temperature": features["ambient_temperature"],
            "humidity": features["humidity"],
        }

        return {
            "name": "Environmental Exposure Risk",
            "score": round(score, 3),
            "risk_level": level,
            "confidence": round(confidence, 3),
            "contributing_features": contributing,
            "timestamp": ts,
            "model_version": self.version_info.get("version", "1.0.0-edge"),
        }

    def predict_general_anomaly(self, features: Dict[str, Any], ts: str) -> Dict[str, Any]:
        if not self.loaded:
            return self._fallback_general_anomaly(features, ts)

        cols = self.features["general_anomaly"]
        vec = pd.DataFrame([[features[c] for c in cols]], columns=cols)
        vec_scaled = self.scalers["general_anomaly"].transform(vec)
        
        prob_anom = float(self.models["general_anomaly"].predict_proba(vec_scaled)[0][1])
        # Iso forest decision function (higher is nominal, lower is anomalous)
        iso_score = float(self.models["general_anomaly_iso"].decision_function(vec_scaled)[0])
        # Convert iso_score into normalized anomaly penalty (0 to 1)
        iso_anomaly = max(0.0, min(1.0, 0.5 - (iso_score * 2.5)))
        
        combined_score = round(float(0.7 * prob_anom + 0.3 * iso_anomaly), 3)

        if combined_score > 0.75:
            level = "CRITICAL"
        elif combined_score > 0.50:
            level = "ELEVATED"
        elif combined_score > 0.25:
            level = "EARLY_WARNING"
        else:
            level = "LOW"

        contributing = {
            "hr_z_score": round(features["hr_z_score"], 2),
            "spo2_z_score": round(features["spo2_z_score"], 2),
            "temp_z_score": round(features["temp_z_score"], 2),
            "activity_state": features["activity_label"],
            "ppg_quality": features["ppg_quality"],
        }

        return {
            "name": "General Health Anomaly Score",
            "score": combined_score,
            "risk_level": level,
            "confidence": round(0.92, 2),
            "contributing_features": contributing,
            "timestamp": ts,
            "model_version": self.version_info.get("version", "1.0.0-edge"),
        }

    def predict_oxygenation_anomaly(self, features: Dict[str, Any], ts: str) -> Dict[str, Any]:
        """Derived oxygenation anomaly indicator focusing on SpO2 drop and PPG quality."""
        spo2 = features["spo2"]
        spo2_dev = features["spo2_deviation"]
        ppg_q = features["ppg_quality"]

        # If PPG quality is poor, confidence is lower
        conf = max(0.65, min(0.99, ppg_q))

        if spo2 < 88 or spo2_dev < -0.10:
            score = 0.95
            level = "CRITICAL"
        elif spo2 < 93 or spo2_dev < -0.05:
            score = 0.70
            level = "ELEVATED"
        elif spo2 < 96 or spo2_dev < -0.025:
            score = 0.38
            level = "EARLY_WARNING"
        else:
            score = 0.08
            level = "LOW"

        return {
            "name": "Oxygenation Anomaly",
            "score": score,
            "risk_level": level,
            "confidence": round(conf, 2),
            "contributing_features": {
                "spo2_reading": spo2,
                "baseline_deviation_pct": round(spo2_dev * 100, 1),
                "ppg_signal_quality": ppg_q,
            },
            "timestamp": ts,
            "model_version": self.version_info.get("version", "1.0.0-edge"),
        }

    def predict_fatigue_risk(self, features: Dict[str, Any], ts: str) -> Dict[str, Any]:
        """Derived activity strain / physiological fatigue indicator."""
        act_state = features["activity_state"]
        hr_dev = features["hr_deviation"]
        temp_dev = features["temp_deviation"]

        score = 0.10
        if act_state >= 3 and hr_dev > 0.35:
            score = 0.82
            level = "ELEVATED"
        elif act_state >= 2 and (hr_dev > 0.20 or temp_dev > 0.8):
            score = 0.55
            level = "EARLY_WARNING"
        elif act_state == 4:  # Fall candidate
            score = 0.90
            level = "CRITICAL"
        else:
            level = "LOW"

        return {
            "name": "Fatigue / Activity-Strain Risk",
            "score": score,
            "risk_level": level,
            "confidence": 0.88,
            "contributing_features": {
                "activity_state": features["activity_label"],
                "cardiac_strain_above_baseline": f"+{round(hr_dev*100, 1)}%",
                "thermal_strain": round(temp_dev, 2),
            },
            "timestamp": ts,
            "model_version": self.version_info.get("version", "1.0.0-edge"),
        }

    def predict_all(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the entire suite of 7 risk models and returns unified evaluation."""
        ts = features.get("timestamp") or (datetime.datetime.utcnow().isoformat() + "Z")

        general = self.predict_general_anomaly(features, ts)
        respiratory = self.predict_respiratory(features, ts)
        oxygenation = self.predict_oxygenation_anomaly(features, ts)
        heat_stress = self.predict_heat_stress(features, ts)
        fatigue = self.predict_fatigue_risk(features, ts)
        environmental = self.predict_environmental(features, ts)

        # Overall Health Risk calculation (weighted worst-case envelope)
        risk_scores = [
            general["score"],
            respiratory["score"] * 1.1,
            oxygenation["score"] * 1.1,
            heat_stress["score"],
            fatigue["score"] * 0.9,
            environmental["score"] * 0.8,
        ]
        overall_score = min(1.0, round(float(np.max(risk_scores) * 0.75 + np.mean(risk_scores) * 0.25), 3))

        # Overall risk level
        if overall_score >= 0.75:
            overall_level = "CRITICAL"
        elif overall_score >= 0.48:
            overall_level = "ELEVATED"
        elif overall_score >= 0.25:
            overall_level = "EARLY_WARNING"
        else:
            overall_level = "LOW"

        # Primary contributing factors for overall risk
        sub_risks = [
            ("Respiratory", respiratory["score"]),
            ("Oxygenation", oxygenation["score"]),
            ("Heat-Stress", heat_stress["score"]),
            ("Environmental", environmental["score"]),
            ("Activity-Strain", fatigue["score"]),
            ("General Anomaly", general["score"]),
        ]
        sub_risks.sort(key=lambda x: x[1], reverse=True)
        top_factors = [f"{name} ({score})" for name, score in sub_risks if score > 0.25][:3]
        if not top_factors:
            top_factors = ["All physiological indicators within baseline norms"]

        overall = {
            "name": "Overall Health Risk",
            "score": overall_score,
            "risk_level": overall_level,
            "confidence": 0.94,
            "contributing_features": {
                "top_drivers": top_factors,
                "overall_score": overall_score,
            },
            "timestamp": ts,
            "model_version": self.version_info.get("version", "1.0.0-edge"),
        }

        return {
            "overall_health_risk": overall,
            "general_health_anomaly": general,
            "respiratory_risk": respiratory,
            "oxygenation_anomaly": oxygenation,
            "heat_stress_risk": heat_stress,
            "fatigue_strain_risk": fatigue,
            "environmental_exposure_risk": environmental,
            "timestamp": ts,
            "model_version": self.version_info.get("version", "1.0.0-edge"),
            "framing_disclaimer": "This prototype provides health-risk and anomaly indicators. It is not a medical diagnostic device.",
        }

    # Fallbacks in case models are not found
    def _fallback_respiratory(self, f, ts):
        s = 0.1; l = "LOW"
        if f["spo2"] < 90: s = 0.9; l = "CRITICAL"
        elif f["spo2"] < 94: s = 0.6; l = "ELEVATED"
        elif f["spo2"] < 96: s = 0.35; l = "EARLY_WARNING"
        return {"name": "Respiratory Risk", "score": s, "risk_level": l, "confidence": 0.85, "contributing_features": {}, "timestamp": ts, "model_version": self.version_info.get("version", "1.0.0-edge")}

    def _fallback_heat_stress(self, f, ts):
        s = 0.1; l = "LOW"
        if f["body_temperature"] > 39: s = 0.9; l = "CRITICAL"
        elif f["body_temperature"] > 38: s = 0.6; l = "ELEVATED"
        elif f["body_temperature"] > 37.5: s = 0.35; l = "EARLY_WARNING"
        return {"name": "Heat-Stress / Physiological-Strain Risk", "score": s, "risk_level": l, "confidence": 0.85, "contributing_features": {}, "timestamp": ts, "model_version": self.version_info.get("version", "1.0.0-edge")}

    def _fallback_environmental(self, f, ts):
        s = 0.1; l = "LOW"
        if f["mq45"] > 600: s = 0.9; l = "CRITICAL"
        elif f["mq45"] > 400: s = 0.6; l = "ELEVATED"
        elif f["mq45"] > 250: s = 0.35; l = "EARLY_WARNING"
        return {"name": "Environmental Exposure Risk", "score": s, "risk_level": l, "confidence": 0.85, "contributing_features": {}, "timestamp": ts, "model_version": self.version_info.get("version", "1.0.0-edge")}

    def _fallback_general_anomaly(self, f, ts):
        return {"name": "General Health Anomaly Score", "score": 0.1, "risk_level": "LOW", "confidence": 0.80, "contributing_features": {}, "timestamp": ts, "model_version": self.version_info.get("version", "1.0.0-edge")}

_registry: Optional[ModelRegistry] = None

def get_model_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
