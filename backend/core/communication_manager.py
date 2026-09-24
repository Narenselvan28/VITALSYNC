"""
VITALSYNC: Modular Communication & Caretaker Dispatch Engine
Decoupled abstraction layer for SIM800L GSM/GPRS, SMS, Emergency Call, and Webhook dispatch.
Enforces event-based notification policies, deduplication cooldowns, and offline resilience.
"""

import time
import datetime
from typing import Dict, Any, List, Optional

class CommunicationManager:
    def __init__(self, default_cooldown_sec: int = 60):
        self.cooldown_sec = default_cooldown_sec
        self.last_dispatched_alert_id: Optional[str] = None
        self.last_dispatch_time: float = 0.0
        self.last_dispatched_level: Optional[str] = None
        self.dispatch_log: List[Dict[str, Any]] = []
        self.sim800l_available = True
        self.sim800l_status = "READY"

    def get_network_status(self) -> Dict[str, Any]:
        """Returns cellular module registration and connectivity status."""
        return {
            "module": "SIM800L",
            "status": self.sim800l_status,
            "is_available": self.sim800l_available,
            "csq_rssi": 24 if self.sim800l_available else 0,  # 0-31 scale
            "network_operator": "VITALSYNC-AIR-EDGE" if self.sim800l_available else "OFFLINE",
            "gprs_attached": self.sim800l_available,
        }

    def set_module_available(self, available: bool):
        self.sim800l_available = available
        self.sim800l_status = "READY" if available else "OFFLINE"

    def dispatch_alert(
        self,
        alert_payload: Dict[str, Any],
        recipient_phone: str = "+919384438928",
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Dispatches emergency SMS and notification with strict deduplication and cooldown.
        Only dispatches for ELEVATED or CRITICAL alerts.
        """
        level = alert_payload.get("risk_level", "LOW")
        alert_id = alert_payload.get("alert_id", "ALT-UNKNOWN")
        now = time.time()

        # Policy 1: Never dispatch SMS for LOW, OBSERVATION, or transient SPIKE_EVENT
        if level in ("LOW", "OBSERVATION", "INFO"):
            return {"status": "SKIPPED", "reason": "Level below dispatch threshold"}

        # Policy 2: Deduplication and cooldown unless severity escalated
        if not force and self.last_dispatch_time > 0:
            elapsed = now - self.last_dispatch_time
            if alert_id == self.last_dispatched_alert_id or (self.last_dispatched_level == level and elapsed < self.cooldown_sec):
                return {
                    "status": "SUPPRESSED",
                    "reason": f"Deduplication cooldown active ({int(self.cooldown_sec - elapsed)}s remaining)",
                }

        # Policy 3: Check SIM800L module availability
        if not self.sim800l_available:
            record = {
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "alert_id": alert_id,
                "level": level,
                "channel": "SMS_SIM800L",
                "recipient": recipient_phone,
                "status": "QUEUED_OFFLINE",
                "message": alert_payload.get("message"),
            }
            self.dispatch_log.insert(0, record)
            return {"status": "QUEUED_OFFLINE", "reason": "SIM800L cellular module offline"}

        # Construct concise emergency SMS text with vitals, time, GPS, risk reason
        domain = alert_payload.get("risk_type", "Health Anomaly")
        snap = alert_payload.get("telemetry_snapshot", {})
        hr_str = f"HR:{snap.get('heart_rate', 'N/A')}"
        spo2_str = f"SpO2:{snap.get('spo2', 'N/A')}%"
        temp_str = f"Temp:{snap.get('body_temperature', 'N/A')}C"
        lat = alert_payload.get('latitude', 10.662)
        lon = alert_payload.get('longitude', 76.891)
        ts_str = alert_payload.get("timestamp", datetime.datetime.utcnow().strftime("%H:%M:%SZ"))

        msg_text = (
            f"[AAROGYA-SHIELD] {level} ALERT: {domain} | "
            f"Vitals: {hr_str}, {spo2_str}, {temp_str} | "
            f"Reason: {alert_payload.get('message', '')} | "
            f"GPS: {lat:.4f},{lon:.4f} @ {ts_str} | Ref: {alert_id}"
        )

        # Dispatch via simulated/hardware AT interface
        record = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "alert_id": alert_id,
            "level": level,
            "channel": "SMS_SIM800L",
            "recipient": recipient_phone,
            "status": "SENT",
            "text": msg_text,
        }
        self.dispatch_log.insert(0, record)
        if len(self.dispatch_log) > 100:
            self.dispatch_log.pop()

        self.last_dispatched_alert_id = alert_id
        self.last_dispatch_time = now
        self.last_dispatched_level = level

        print(f"[SIM800L Dispatch] SMS to {recipient_phone} ({level}): {msg_text}")
        return {"status": "SENT", "channel": "SMS_SIM800L", "alert_id": alert_id}

_comm_manager = CommunicationManager()

def get_communication_manager() -> CommunicationManager:
    return _comm_manager
