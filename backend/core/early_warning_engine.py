"""
VITALSYNC: Early-Warning & Trend Persistence Engine
Coordinates temporal filtering across decoupled risk domains.
Dampens transient noise, tracks multi-signal persistence, and drives the AlertStateMachine.
"""

from typing import Dict, Any, List, Tuple
from collections import deque
import datetime
import time

from backend.core.alert_state_machine import get_alert_state_machine

class EarlyWarningState:
    def __init__(self, device_id: str, persistence_window: int = 10):
        self.device_id = device_id
        self.persistence_window = persistence_window
        self.history = deque(maxlen=persistence_window)
        self.consecutive_abnormal_count = 0
        self.abnormal_start_time: float = 0.0
        self.sm = get_alert_state_machine()

    def evaluate(self, ml_predictions: Dict[str, Any], features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Integrates raw ML domain predictions into temporal persistence and state machine.
        """
        overall = ml_predictions["overall_health_risk"]
        raw_score = overall["score"]
        raw_level = overall["risk_level"]
        primary_domain = overall.get("primary_domain", "General Physiological")
        primary_reason = overall.get("primary_reason", "Parameters tracking within baseline.")
        now = time.time()

        domains = ml_predictions.get("risk_domains", {})
        fall_info = domains.get("fall_event", {})
        is_fall_confirmed = fall_info.get("is_confirmed", False)
        is_fall_candidate = fall_info.get("is_candidate", False)

        # Track persistence of non-LOW readings
        if raw_level not in ("LOW", "OBSERVATION"):
            if self.consecutive_abnormal_count == 0:
                self.abnormal_start_time = now
            self.consecutive_abnormal_count += 1
        else:
            self.consecutive_abnormal_count = max(0, self.consecutive_abnormal_count - 1)
            if self.consecutive_abnormal_count == 0:
                self.abnormal_start_time = 0.0

        persistence_duration_sec = (now - self.abnormal_start_time) if self.abnormal_start_time > 0 else 0.0

        # TRANSIENT SPIKE DAMPENING RULE:
        # If a single reading spikes to CRITICAL (e.g. HR=198 for 2s, or hot beverage touch),
        # but persistence count < 3 and NOT a confirmed fall or severe hypoxia (SpO2 < 86):
        # Dampen the score to prevent premature emergency alerts.
        adjusted_score = raw_score
        spo2 = features.get("spo2", 98.0)
        ppg_q = features.get("ppg_quality", 0.95)
        sensor_conf = features.get("overall_sensor_confidence", 1.0)
        is_transient_thermal = features.get("is_transient_thermal", False)

        if is_transient_thermal:
            # Hot beverage: force dampened score
            adjusted_score = min(adjusted_score, 0.20)
            primary_reason = "Transient thermal contact spike detected. Rapid recovery in progress."
        elif ppg_q < 0.50 or sensor_conf < 0.60:
            # Bad sensor quality: NEVER allow to trigger critical emergency!
            adjusted_score = min(adjusted_score, 0.45)
            primary_reason = f"Reduced sensor signal quality (PPG {ppg_q:.2f}). Emergency alerts suspended pending clean signal."
        elif raw_level == "CRITICAL" and not is_fall_confirmed:
            if self.consecutive_abnormal_count < 2:
                adjusted_score = min(raw_score, 0.55)  # Cap pending persistence confirmation
                primary_reason += " (Verifying persistence: transient spike dampening active)"

        # Feed to Alert State Machine with Hysteresis
        sm_eval = self.sm.evaluate(
            device_id=self.device_id,
            overall_score=adjusted_score,
            highest_domain=primary_domain,
            highest_domain_score=adjusted_score,
            reason=primary_reason,
            is_fall_confirmed=is_fall_confirmed,
            is_fall_candidate=is_fall_candidate,
        )

        return {
            "escalated_level": sm_eval["current_state"],
            "raw_level": raw_level,
            "raw_score": raw_score,
            "adjusted_score": round(adjusted_score, 3),
            "state_machine": sm_eval,
            "primary_domain": primary_domain,
            "persistence_count": self.consecutive_abnormal_count,
            "persistence_duration_sec": round(persistence_duration_sec, 1),
            "reasons": [primary_reason],
            "timeline": sm_eval["timeline"],
            "timestamp": features.get("timestamp", datetime.datetime.utcnow().isoformat() + "Z"),
        }

_ew_states: Dict[str, EarlyWarningState] = {}

def get_early_warning_state(device_id: str = "ESP32-001") -> EarlyWarningState:
    if device_id not in _ew_states:
        _ew_states[device_id] = EarlyWarningState(device_id)
    return _ew_states[device_id]
