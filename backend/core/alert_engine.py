"""
AAROGYA-SHIELD: Caretaker Alert System
Generates, stores, escalates, and acknowledges caretaker notifications.
Maintains deduplication cooldowns and provides modular webhooks for SMS/WhatsApp/Push dispatch.
"""

import uuid
import datetime
from typing import Dict, Any, List, Optional
from collections import deque

class AlertEngine:
    def __init__(self, cooldown_seconds: int = 15):
        self.alerts_history: List[Dict[str, Any]] = []
        self.active_alert: Optional[Dict[str, Any]] = None
        self.last_alert_time: Optional[datetime.datetime] = None
        self.last_alert_level: Optional[str] = None
        self.cooldown_seconds = cooldown_seconds

    def check_and_create_alert(
        self,
        device_id: str,
        escalated_eval: Dict[str, Any],
        ml_predictions: Dict[str, Any],
        features: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates whether a caretaker alert should be emitted.
        Fires for EARLY_WARNING, ELEVATED, and CRITICAL with intelligent deduplication.
        """
        level = escalated_eval["escalated_level"]
        if level == "LOW":
            return None

        now = datetime.datetime.utcnow()

        # Check cooldown if the level hasn't escalated
        if self.last_alert_time and self.last_alert_level == level:
            elapsed = (now - self.last_alert_time).total_seconds()
            if elapsed < self.cooldown_seconds:
                return self.active_alert

        # Determine primary risk type
        top_type = "Physiological Anomaly"
        respiratory_level = ml_predictions["respiratory_risk"]["risk_level"]
        heat_level = ml_predictions["heat_stress_risk"]["risk_level"]
        env_level = ml_predictions["environmental_exposure_risk"]["risk_level"]

        if features.get("activity_state") == 4 or features.get("is_fall_candidate") or features.get("activity_level") == "FALL_CANDIDATE":
            top_type = "Fall Candidate Anomaly"
        elif respiratory_level in ["ELEVATED", "CRITICAL"]:
            top_type = "Respiratory Risk"
        elif heat_level in ["ELEVATED", "CRITICAL"]:
            top_type = "Heat-Stress Risk"
        elif env_level in ["ELEVATED", "CRITICAL"]:
            top_type = "Environmental Exposure Risk"

        # Construct standard prototype message
        if level == "EARLY_WARNING":
            message = f"{top_type} is beginning to increase above personal baseline."
        elif level == "ELEVATED":
            message = "Multiple physiological and environmental parameters are deviating from baseline."
        else:
            message = "Critical physiological anomaly detected. Immediate attention required."

        alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
        alert_payload = {
            "alert_id": alert_id,
            "device_id": device_id,
            "patient_id": f"PATIENT-{device_id}",
            "timestamp": now.isoformat() + "Z",
            "risk_type": top_type,
            "risk_level": level,
            "message": message,
            "contributing_parameters": escalated_eval.get("reasons", []),
            "latitude": features.get("latitude", 10.662),
            "longitude": features.get("longitude", 76.891),
            "acknowledged": False,
            "acknowledged_at": None,
            "telemetry_snapshot": {
                "heart_rate": features.get("heart_rate"),
                "spo2": features.get("spo2"),
                "body_temperature": features.get("body_temperature"),
                "ambient_temperature": features.get("ambient_temperature"),
                "humidity": features.get("humidity"),
                "mq45": features.get("mq45"),
                "activity": features.get("activity_level") or features.get("activity_label"),
            }
        }

        self.active_alert = alert_payload
        self.alerts_history.insert(0, alert_payload)
        # Retain last 200 alerts in memory
        if len(self.alerts_history) > 200:
            self.alerts_history.pop()

        self.last_alert_time = now
        self.last_alert_level = level

        # Trigger modular caretaker notification hook
        self._dispatch_caretaker_notification(alert_payload)

        return alert_payload

    def acknowledge_alert(self, alert_id: str) -> Optional[Dict[str, Any]]:
        for alert in self.alerts_history:
            if alert["alert_id"] == alert_id:
                alert["acknowledged"] = True
                alert["acknowledged_at"] = datetime.datetime.utcnow().isoformat() + "Z"
                if self.active_alert and self.active_alert["alert_id"] == alert_id:
                    self.active_alert["acknowledged"] = True
                    self.active_alert["acknowledged_at"] = alert["acknowledged_at"]
                return alert
        return None

    def get_latest_alert(self) -> Optional[Dict[str, Any]]:
        return self.active_alert

    def get_all_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.alerts_history[:limit]

    def _dispatch_caretaker_notification(self, alert: Dict[str, Any]):
        """Modular hook for future SMS / WhatsApp / Push dispatch."""
        print(f"[CaretakerAlert] [{alert['risk_level']}] {alert['risk_type']}: {alert['message']} (ID: {alert['alert_id']})")

_alert_engine: Optional[AlertEngine] = None

def get_alert_engine() -> AlertEngine:
    global _alert_engine
    if _alert_engine is None:
        _alert_engine = AlertEngine()
    return _alert_engine
