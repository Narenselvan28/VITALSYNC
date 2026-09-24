"""
VITALSYNC: Caretaker Alert System
Generates, stores, escalates, and acknowledges caretaker notifications.
Integrates with CommunicationManager (SIM800L / SMS / Cellular) and enforces
strict deduplication cooldowns and auto-clearing upon physiological recovery.
"""

import uuid
import datetime
from typing import Dict, Any, List, Optional

from backend.core.communication_manager import get_communication_manager

class AlertEngine:
    def __init__(self, cooldown_seconds: int = 30):
        self.alerts_history: List[Dict[str, Any]] = []
        self.active_alert: Optional[Dict[str, Any]] = None
        self.last_alert_time: Optional[datetime.datetime] = None
        self.last_alert_level: Optional[str] = None
        self.cooldown_seconds = cooldown_seconds
        self.comm_manager = get_communication_manager()

    def reset(self):
        """Resets active alert state."""
        self.active_alert = None
        self.last_alert_time = None
        self.last_alert_level = None

    def check_and_create_alert(
        self,
        device_id: str,
        escalated_eval: Dict[str, Any],
        ml_predictions: Dict[str, Any],
        features: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates whether a caretaker alert should be emitted.
        Only fires for ELEVATED and CRITICAL states with deduplication.
        Automatically clears active_alert when system transitions to RECOVERING or NORMAL.
        """
        level = escalated_eval["escalated_level"]
        now = datetime.datetime.utcnow()

        # RECOVERY / CLEARING LOGIC:
        if level in ("NORMAL", "OBSERVATION", "RECOVERING"):
            if self.active_alert and not self.active_alert.get("cleared"):
                self.active_alert["cleared"] = True
                self.active_alert["cleared_at"] = now.isoformat() + "Z"
                self.active_alert["status"] = "RECOVERED"
            if level == "NORMAL":
                self.active_alert = None
            return None

        # Check cooldown if the level hasn't escalated
        if self.last_alert_time and self.last_alert_level == level:
            elapsed = (now - self.last_alert_time).total_seconds()
            if elapsed < self.cooldown_seconds:
                return self.active_alert

        primary_domain = escalated_eval.get("primary_domain", "Physiological Anomaly")
        reasons = escalated_eval.get("reasons", ["Parameter deviation from baseline."])
        reason_msg = reasons[0] if reasons else "Multi-parameter baseline deviation."

        # Construct concise emergency message
        if level == "ELEVATED":
            message = f"{primary_domain} is elevated above baseline. {reason_msg}"
        else:
            message = f"CRITICAL: {primary_domain}. Immediate attention required. {reason_msg}"

        alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
        alert_payload = {
            "alert_id": alert_id,
            "device_id": device_id,
            "patient_id": f"PATIENT-{device_id}",
            "timestamp": now.isoformat() + "Z",
            "risk_type": primary_domain,
            "risk_level": level,
            "message": message,
            "contributing_parameters": reasons,
            "latitude": features.get("latitude", 10.662),
            "longitude": features.get("longitude", 76.891),
            "acknowledged": False,
            "acknowledged_at": None,
            "cleared": False,
            "status": "ACTIVE",
            "telemetry_snapshot": {
                "heart_rate": features.get("heart_rate"),
                "spo2": features.get("spo2"),
                "body_temperature": features.get("body_temperature"),
                "ambient_temperature": features.get("ambient_temperature"),
                "humidity": features.get("humidity"),
                "mq45": features.get("mq45"),
                "activity": features.get("activity_level") or features.get("activity_label"),
            },
        }

        self.active_alert = alert_payload
        self.alerts_history.insert(0, alert_payload)
        if len(self.alerts_history) > 200:
            self.alerts_history.pop()

        self.last_alert_time = now
        self.last_alert_level = level

        # Dispatch via CommunicationManager (SIM800L SMS / Cellular)
        self.comm_manager.dispatch_alert(alert_payload)

        return alert_payload

    def acknowledge_alert(self, alert_id: str) -> Optional[Dict[str, Any]]:
        for alert in self.alerts_history:
            if alert["alert_id"] == alert_id:
                alert["acknowledged"] = True
                alert["acknowledged_at"] = datetime.datetime.utcnow().isoformat() + "Z"
                alert["status"] = "ACKNOWLEDGED"
                if self.active_alert and self.active_alert["alert_id"] == alert_id:
                    self.active_alert["acknowledged"] = True
                    self.active_alert["acknowledged_at"] = alert["acknowledged_at"]
                return alert
        return None

    def get_latest_alert(self) -> Optional[Dict[str, Any]]:
        return self.active_alert

    def get_all_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.alerts_history[:limit]

_alert_engine: Optional[AlertEngine] = None

def get_alert_engine() -> AlertEngine:
    global _alert_engine
    if _alert_engine is None:
        _alert_engine = AlertEngine()
    return _alert_engine
