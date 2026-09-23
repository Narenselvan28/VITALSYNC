"""
AAROGYA-SHIELD: Early-Warning & Trend Escalation Engine
Applies temporal persistence filters and multi-parameter synergy rules
to prevent noise-induced false alarms and ensure transparent, explainable escalation.
"""

from typing import Dict, Any, List, Tuple
from collections import deque
import datetime

SEVERITY_ORDER = {
    "LOW": 0,
    "EARLY_WARNING": 1,
    "ELEVATED": 2,
    "CRITICAL": 3,
}

REVERSE_SEVERITY = {v: k for k, v in SEVERITY_ORDER.items()}

class EarlyWarningState:
    def __init__(self, device_id: str, persistence_window: int = 5):
        self.device_id = device_id
        self.persistence_window = persistence_window
        # History of raw risk evaluations
        self.history = deque(maxlen=persistence_window)
        self.current_escalated_level = "LOW"
        self.consecutive_abnormal_count = 0
        now_ts = datetime.datetime.utcnow()
        self.timeline: List[Dict[str, Any]] = [
            {
                "time": now_ts.strftime("%H:%M:%S"),
                "timestamp": now_ts.isoformat() + "Z",
                "level": "LOW",
                "event": "NORMAL",
                "details": "All physiological parameters tracking within personal baseline.",
            }
        ]

    def get_timeline(self, limit: int = 30) -> List[Dict[str, Any]]:
        return list(reversed(self.timeline))[:limit]

    def evaluate(self, ml_predictions: Dict[str, Any], features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates current ML predictions against temporal history and multi-parameter synergy.
        Returns escalated risk states with transparent reasoning and timeline events.
        """
        raw_overall = ml_predictions["overall_health_risk"]
        raw_level = raw_overall["risk_level"]
        raw_score = raw_overall["score"]
        
        self.history.append({
            "level": raw_level,
            "score": raw_score,
            "features": features,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        })

        # Track persistence of non-LOW readings
        if raw_level != "LOW":
            self.consecutive_abnormal_count += 1
        else:
            self.consecutive_abnormal_count = max(0, self.consecutive_abnormal_count - 1)

        # Multi-parameter deviation indicators
        spo2 = features.get("spo2", 98.0)
        spo2_dev = features.get("spo2_deviation", 0.0)
        hr = features.get("heart_rate", 75.0)
        hr_dev = features.get("hr_deviation", 0.0)
        body_temp = features.get("body_temperature", 36.8)
        temp_dev = features.get("temp_deviation", 0.0)
        mq45 = features.get("mq45", 180.0)
        act_state = features.get("activity_state", 0)

        reasons = []
        deviating_count = 0

        # Check parameter 1: SpO2
        if spo2 < 90 or spo2_dev < -0.07:
            reasons.append(f"SpO2 severely depressed ({spo2}%, {round(spo2_dev*100, 1)}% from baseline)")
            deviating_count += 2
        elif spo2 < 95 or spo2_dev < -0.03:
            reasons.append(f"SpO2 trending below personal baseline ({spo2}%, {round(spo2_dev*100, 1)}%)")
            deviating_count += 1

        # Check parameter 2: Heart Rate
        if hr > 130 or hr_dev > 0.40:
            reasons.append(f"Heart rate significantly elevated ({int(hr)} BPM, +{round(hr_dev*100, 1)}% from baseline)")
            deviating_count += 2
        elif hr > 95 or hr_dev > 0.18:
            reasons.append(f"Heart rate elevated above resting baseline ({int(hr)} BPM, +{round(hr_dev*100, 1)}%)")
            deviating_count += 1

        # Check parameter 3: Body Temperature
        if body_temp > 38.8 or temp_dev > 1.8:
            reasons.append(f"High thermal strain/fever ({body_temp}°C, +{round(temp_dev, 1)}°C from baseline)")
            deviating_count += 2
        elif body_temp > 37.6 or temp_dev > 0.8:
            reasons.append(f"Body temperature trending above baseline ({body_temp}°C, +{round(temp_dev, 1)}°C)")
            deviating_count += 1

        # Check parameter 4: Environmental MQ-45
        if mq45 > 600:
            reasons.append(f"Severe environmental gas/air exposure index ({int(mq45)})")
            deviating_count += 2
        elif mq45 > 350:
            reasons.append(f"Elevated environmental exposure indicator ({int(mq45)})")
            deviating_count += 1

        # Check parameter 5: Fall Candidate
        if act_state == 4:
            reasons.append("Sudden high-g acceleration impact detected (potential fall event)")
            deviating_count += 3

        # Escalation Logic:
        # 1. Single sample noise dampening:
        # If raw_level is CRITICAL but persistence count is only 1 and not an immediate fall/severe hypoxia:
        # Damped to ELEVATED pending persistence confirmation.
        escalated_level = raw_level

        if raw_level == "CRITICAL":
            if self.consecutive_abnormal_count < 2 and act_state != 4 and spo2 >= 85:
                escalated_level = "ELEVATED"
                reasons.append("Verifying critical persistence (single-reading transient dampening active)")
            else:
                escalated_level = "CRITICAL"
        elif raw_level == "ELEVATED":
            # If multiple independent parameters deviate and persistent >= 3, escalate to CRITICAL
            if deviating_count >= 4 and self.consecutive_abnormal_count >= 3:
                escalated_level = "CRITICAL"
                reasons.append("Multi-system persistent deviation escalated to critical threshold")
            else:
                escalated_level = "ELEVATED"
        elif raw_level == "EARLY_WARNING":
            # If multiple parameters deviate simultaneously, escalate EARLY_WARNING -> ELEVATED
            if deviating_count >= 2:
                escalated_level = "ELEVATED"
                reasons.append("Concurrent multi-parameter deviation escalated risk level to ELEVATED")
            else:
                escalated_level = "EARLY_WARNING"
        else: # LOW
            # If a sudden fall candidate or severe hypoxia happens even if model lag
            if act_state == 4:
                escalated_level = "CRITICAL"
            elif deviating_count >= 2:
                escalated_level = "EARLY_WARNING"
                reasons.append("Early multi-parameter baseline deviation detected")
            else:
                escalated_level = "LOW"
                reasons.append("All primary physiological and environmental parameters within personal baseline")

        # Track timeline event if state escalated or de-escalated
        prev_level = self.current_escalated_level
        self.current_escalated_level = escalated_level

        now = datetime.datetime.utcnow()
        if escalated_level != prev_level:
            event_name = f"Overall Risk → {escalated_level.replace('_', ' ')}"
            detail_msg = reasons[0] if reasons else f"State transitioned from {prev_level} to {escalated_level}"
            self.timeline.append({
                "time": now.strftime("%H:%M:%S"),
                "timestamp": now.isoformat() + "Z",
                "level": escalated_level,
                "event": event_name,
                "details": detail_msg,
            })
            if len(self.timeline) > 60:
                self.timeline.pop(0)

        return {
            "escalated_level": escalated_level,
            "raw_level": raw_level,
            "persistence_count": self.consecutive_abnormal_count,
            "deviating_parameter_count": deviating_count,
            "reasons": reasons,
            "timeline": self.get_timeline(15),
            "timestamp": now.isoformat() + "Z",
        }

_early_warning_states: Dict[str, EarlyWarningState] = {}

def get_early_warning_state(device_id: str = "ESP32-001") -> EarlyWarningState:
    if device_id not in _early_warning_states:
        _early_warning_states[device_id] = EarlyWarningState(device_id)
    return _early_warning_states[device_id]
