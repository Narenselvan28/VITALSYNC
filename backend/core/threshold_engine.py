"""
AAROGYA-SHIELD: Dynamic 3-Level Threshold & Sensitivity Engine
Separates clinical reference guidelines from personal learned baselines and ML probabilities:
- Level 1: Clinical Reference Thresholds (sourced, versioned, reviewed)
- Level 2: Personal Learned Baseline (mean, median, std, percentiles, dynamic deviation)
- Level 3: Temporal ML Anomaly Probabilities
Enforces non-diagnostic clinical context reasoning and transparent decision tracing.
"""

import os
import json
from typing import Dict, Any, List, Optional
from backend.core.patient_profile import get_patient_profile_manager

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "clinical_thresholds.json")

class ThresholdEngine:
    def __init__(self, config_path: str = CONFIG_PATH):
        self.config_path = config_path
        self.config: Dict[str, Any] = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ThresholdEngine] Failed to load config ({e}). Using minimal defaults.")
        return {"profiles": {"default": {}}}

    def get_clinical_references(self, profile_name: str = "default") -> Dict[str, Any]:
        """Returns structured, versioned clinical reference thresholds with metadata."""
        profiles = self.config.get("profiles", {})
        return profiles.get(profile_name, profiles.get("default", {}))

    def evaluate_vitals(
        self,
        vitals: Dict[str, float],
        baseline_stats: Dict[str, Any],
        ml_predictions: Dict[str, Any],
        sensor_qualities: Dict[str, float],
        activity_context: Dict[str, Any],
        device_id: str = "ESP32-001",
    ) -> Dict[str, Any]:
        """
        Executes the 3-Level Dynamic Threshold Evaluation:
        Level 1: Clinical Reference Thresholds
        Level 2: Personal Baseline Deviations
        Level 3: Temporal ML Anomaly Probabilities
        Returns domain-specific risk adjustments, sensitivity factors, and transparent decision sources.
        """
        profile_mgr = get_patient_profile_manager(device_id)
        profile = profile_mgr.get_profile()
        conditions = profile.get("conditions", ["none"])
        active_contexts = profile_mgr.get_active_condition_contexts()

        hr = float(vitals.get("heart_rate", 75.0))
        spo2 = float(vitals.get("spo2", 98.0))
        temp = float(vitals.get("body_temperature", 36.7))
        amb_temp = float(vitals.get("ambient_temperature", 28.0))
        mq45 = float(vitals.get("mq45", 180.0))

        act_state = activity_context.get("state", "REST")
        is_exercising = act_state in ("WALKING", "RUNNING", "RUNNING_HIGH_ACTIVITY")

        ppg_qual_val = sensor_qualities.get("ppg_quality", sensor_qualities.get("ppg", 0.95))
        if isinstance(ppg_qual_val, str):
            ppg_qual = 0.35 if ppg_qual_val in ("WEAK", "INVALID") else (0.70 if ppg_qual_val == "FAIR" else 1.0)
        elif isinstance(ppg_qual_val, (int, float)):
            ppg_qual = float(ppg_qual_val)
        else:
            ppg_qual = 0.95

        # -------------------------------------------------------------
        # 1. Condition Sensitivity Multipliers
        # -------------------------------------------------------------
        hr_sensitivity = 1.0
        spo2_sensitivity = 1.0
        env_sensitivity = 1.0
        recovery_sensitivity = 1.0
        special_notices = []

        if "asthma" in conditions or "copd" in conditions or "other_respiratory" in conditions:
            spo2_sensitivity = 1.35
            env_sensitivity = 1.30
            special_notices.append("Respiratory profile active: heightened SpO2 drop sensitivity.")

        if "cardiovascular" in conditions or "hypertension" in conditions or "other_cardiovascular" in conditions:
            hr_sensitivity = 1.30
            recovery_sensitivity = 1.25
            special_notices.append("Cardiovascular profile active: heightened resting HR deviation sensitivity.")

        if "diabetes" in conditions:
            special_notices.append("Metabolic context note: Wearable sensors cannot measure blood glucose.")

        if "hypertension" in conditions:
            special_notices.append("Hypertension context note: Optical PPG cannot infer blood pressure.")

        # -------------------------------------------------------------
        # 2. Level 1: Clinical Reference Check
        # -------------------------------------------------------------
        def_refs = self.get_clinical_references("default")
        hr_refs = def_refs.get("heart_rate", {})
        spo2_refs = def_refs.get("spo2", {})
        temp_refs = def_refs.get("body_temperature", {})

        hr_ref_exceeded = False
        hr_ref_severe = False
        spo2_ref_exceeded = False
        spo2_ref_critical = False
        temp_ref_exceeded = False

        ref_reasons = []

        # Heart Rate References
        hr_tac_thresh = hr_refs.get("tachycardia_threshold", {}).get("value", 105.0)
        hr_sev_thresh = hr_refs.get("severe_tachycardia_threshold", {}).get("value", 140.0)
        hr_brady_thresh = hr_refs.get("bradycardia_threshold", {}).get("value", 50.0)

        # If cardiovascular condition, check cardiac specific threshold
        if "cardiovascular" in conditions:
            cardiac_refs = self.get_clinical_references("cardiovascular").get("heart_rate", {})
            hr_tac_thresh = cardiac_refs.get("tachycardia_alert", {}).get("value", 100.0)
            hr_sev_thresh = cardiac_refs.get("critical_tachycardia", {}).get("value", 130.0)

        if not is_exercising:
            if hr >= hr_sev_thresh:
                hr_ref_severe = True
                hr_ref_exceeded = True
                ref_reasons.append(f"HR ({int(hr)} bpm) exceeds clinical severe tachycardia reference ({int(hr_sev_thresh)} bpm)")
            elif hr >= hr_tac_thresh:
                hr_ref_exceeded = True
                ref_reasons.append(f"Resting HR ({int(hr)} bpm) exceeds clinical tachycardia reference ({int(hr_tac_thresh)} bpm)")
            elif hr < hr_brady_thresh:
                hr_ref_exceeded = True
                ref_reasons.append(f"Resting HR ({int(hr)} bpm) below clinical bradycardia reference ({int(hr_brady_thresh)} bpm)")

        # SpO2 References
        spo2_mild = spo2_refs.get("mild_hypoxemia", {}).get("value", 93.0)
        spo2_crit = spo2_refs.get("critical_hypoxemia", {}).get("value", 88.0)

        # If COPD condition, apply GOLD target band (88-92% normal target for retainers)
        if "copd" in conditions:
            copd_refs = self.get_clinical_references("copd").get("spo2", {})
            spo2_crit = copd_refs.get("critical_desaturation", {}).get("value", 85.0)
            spo2_mild = copd_refs.get("target_range_min", {}).get("value", 88.0)

        if spo2 <= spo2_crit:
            spo2_ref_critical = True
            spo2_ref_exceeded = True
            ref_reasons.append(f"SpO2 ({spo2:.1f}%) in critical hypoxemia range (ref <= {spo2_crit}%)")
        elif spo2 <= spo2_mild:
            spo2_ref_exceeded = True
            ref_reasons.append(f"SpO2 ({spo2:.1f}%) in mild hypoxemia reference band (ref <= {spo2_mild}%)")

        # Temperature References
        temp_pyrexia = temp_refs.get("low_grade_pyrexia", {}).get("value", 37.8)
        if temp >= temp_pyrexia:
            temp_ref_exceeded = True
            ref_reasons.append(f"Body temperature ({temp:.1f}°C) exceeds pyrexia reference ({temp_pyrexia}°C)")

        # -------------------------------------------------------------
        # 3. Level 2: Personal Baseline Check
        # -------------------------------------------------------------
        hr_base_stats = baseline_stats.get("heart_rate", {})
        spo2_base_stats = baseline_stats.get("spo2", {})
        temp_base_stats = baseline_stats.get("body_temperature", {})

        hr_base_mean = hr_base_stats.get("baseline_mean", 72.0)
        hr_base_std = max(2.0, hr_base_stats.get("baseline_std", 6.0))
        spo2_base_mean = spo2_base_stats.get("baseline_mean", 98.0)
        temp_base_mean = temp_base_stats.get("baseline_mean", 36.7)

        hr_z = (hr - hr_base_mean) / hr_base_std if not is_exercising else 0.0
        hr_baseline_shift = abs(hr_z) >= 2.5
        spo2_baseline_shift = (spo2_base_mean - spo2) >= (3.5 / spo2_sensitivity)
        temp_baseline_shift = abs(temp - temp_base_mean) >= 1.2

        baseline_reasons = []
        if hr_baseline_shift:
            baseline_reasons.append(f"HR differs by {hr_z:+.1f}σ from personal resting mean ({hr_base_mean:.1f} bpm)")
        if spo2_baseline_shift:
            baseline_reasons.append(f"SpO2 dropped {spo2_base_mean - spo2:.1f}% below personal baseline ({spo2_base_mean:.1f}%)")
        if temp_baseline_shift:
            baseline_reasons.append(f"Body temp differs by {temp - temp_base_mean:+.1f}°C from personal baseline ({temp_base_mean:.1f}°C)")

        # -------------------------------------------------------------
        # 4. Level 3: ML Anomaly Models & Transparent Decision Tracing
        # -------------------------------------------------------------
        ml_domains = ml_predictions.get("risk_domains", {})
        ml_hr_score = ml_domains.get("heart_rate_anomaly", {}).get("score", 0.08)
        ml_oxy_score = ml_domains.get("oxygenation_anomaly", {}).get("score", 0.05)
        ml_resp_score = ml_domains.get("respiratory_risk", {}).get("score", 0.05)

        decision_sources = []
        if hr_ref_exceeded or spo2_ref_exceeded or temp_ref_exceeded:
            decision_sources.append("REFERENCE_THRESHOLD")
        if hr_baseline_shift or spo2_baseline_shift or temp_baseline_shift:
            decision_sources.append("PERSONAL_BASELINE")
        if ml_hr_score > 0.40 or ml_oxy_score > 0.40 or ml_resp_score > 0.40:
            decision_sources.append("ML_MODEL")
        if is_exercising:
            decision_sources.append("ACTIVITY_CONTEXT")
        if mq45 > 400 or amb_temp > 35:
            decision_sources.append("ENVIRONMENTAL_CONTEXT")
        if ppg_qual < 0.70:
            decision_sources.append("SENSOR_QUALITY_WARNING")

        # -------------------------------------------------------------
        # 5. Personalized Domain Risk Fusion
        # -------------------------------------------------------------
        personalized_domain_risks = {
            "heart_rate": round(min(1.0, ml_hr_score * hr_sensitivity), 3),
            "oxygenation": round(min(1.0, ml_oxy_score * spo2_sensitivity), 3),
            "respiratory": round(min(1.0, ml_resp_score * spo2_sensitivity * (1.2 if env_sensitivity > 1.0 and mq45 > 350 else 1.0)), 3),
            "thermal": round(ml_domains.get("heat_stress_risk", {}).get("score", 0.08), 3),
            "activity": round(ml_domains.get("activity_strain", {}).get("score", 0.05), 3),
            "environment": round(ml_domains.get("environmental_exposure", {}).get("score", 0.08), 3),
        }

        return {
            "personalized": True,
            "profile_version": profile.get("profile_version", "1.0"),
            "conditions": conditions,
            "active_condition_contexts": active_contexts,
            "sensitivity_factors": {
                "heart_rate": hr_sensitivity,
                "oxygenation": spo2_sensitivity,
                "environmental": env_sensitivity,
                "recovery": recovery_sensitivity,
            },
            "decision_sources": decision_sources or ["NOMINAL_TRACKING"],
            "clinical_reference_reasons": ref_reasons,
            "personal_baseline_reasons": baseline_reasons,
            "special_notices": special_notices,
            "domain_risks": personalized_domain_risks,
        }

_threshold_engine = ThresholdEngine()

def get_threshold_engine() -> ThresholdEngine:
    return _threshold_engine
