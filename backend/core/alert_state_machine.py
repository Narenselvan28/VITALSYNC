"""
VITALSYNC: Alert State Machine with Hysteresis & Auto-Clearing Recovery
Manages health alert lifecycles:
NORMAL -> OBSERVATION -> EARLY_WARNING -> ELEVATED -> CRITICAL -> RECOVERING -> NORMAL.
Prevents oscillation using decoupled entry and exit thresholds (hysteresis).
Ensures transient spikes naturally recover and clear rather than latching forever.
"""

import time
import datetime
from typing import Dict, Any, List, Optional
from collections import deque

class AlertStateMachine:
    def __init__(
        self,
        elevated_enter_thresh: float = 0.65,
        elevated_exit_thresh: float = 0.45,
        critical_enter_thresh: float = 0.80,
        critical_exit_thresh: float = 0.60,
        recovery_duration_sec: float = 8.0,
    ):
        self.elevated_enter = elevated_enter_thresh
        self.elevated_exit = elevated_exit_thresh
        self.critical_enter = critical_enter_thresh
        self.critical_exit = critical_exit_thresh
        self.recovery_duration_sec = recovery_duration_sec

        # State per device
        self._states: Dict[str, Dict[str, Any]] = {}

    def _init_device(self, device_id: str):
        now_ts = datetime.datetime.utcnow().isoformat() + "Z"
        self._states[device_id] = {
            "current_state": "NORMAL",
            "active_domain": None,
            "trigger_reason": "All parameters normal",
            "peak_score": 0.0,
            "current_score": 0.0,
            "created_at": now_ts,
            "last_updated_at": now_ts,
            "recovery_started_at": None,
            "recovery_start_time": None,
            "cleared_at": None,
            "active_alert_id": None,
            "score_history": deque(maxlen=20),
            "state_timeline": deque(maxlen=40),
        }

    def reset(self, device_id: Optional[str] = None):
        """Resets the state machine for testing or re-initialization."""
        if device_id:
            self._init_device(device_id)
        else:
            self._states.clear()

    def evaluate(
        self,
        device_id: str,
        overall_score: float,
        highest_domain: str,
        highest_domain_score: float,
        reason: str,
        is_fall_confirmed: bool = False,
        is_fall_candidate: bool = False,
    ) -> Dict[str, Any]:
        """
        Updates the alert state machine with hysteresis.
        Returns the current state and transition details.
        """
        if device_id not in self._states:
            self._init_device(device_id)

        st = self._states[device_id]
        now = time.time()
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"
        prev_state = st["current_state"]

        st["current_score"] = round(overall_score, 3)
        st["score_history"].append(overall_score)
        st["last_updated_at"] = now_iso

        # Immediate Fall Override
        if is_fall_confirmed:
            target_state = "CRITICAL"
            target_domain = "Fall / Immobility Event"
            reason = "Confirmed Fall Event detected with post-event immobility"
        elif is_fall_candidate:
            target_state = "ELEVATED"
            target_domain = "Fall / Immobility Event"
            reason = "High-g impact followed by immobility (Fall candidate verification)"
        else:
            # HYSTERESIS TRANSITION LOGIC
            target_domain = highest_domain

            if prev_state == "CRITICAL":
                # Exit critical only when score drops below critical_exit
                if overall_score < self.critical_exit:
                    if overall_score <= self.elevated_exit:
                        target_state = "RECOVERING"
                    else:
                        target_state = "ELEVATED"
                else:
                    target_state = "CRITICAL"

            elif prev_state == "ELEVATED":
                if overall_score >= self.critical_enter:
                    target_state = "CRITICAL"
                elif overall_score <= self.elevated_exit:
                    target_state = "RECOVERING"
                else:
                    target_state = "ELEVATED"

            elif prev_state == "EARLY_WARNING":
                if overall_score >= self.critical_enter:
                    target_state = "CRITICAL"
                elif overall_score >= self.elevated_enter:
                    target_state = "ELEVATED"
                elif overall_score < 0.22:
                    target_state = "RECOVERING"
                else:
                    target_state = "EARLY_WARNING"

            elif prev_state == "RECOVERING":
                # In recovering, if score remains low for duration, return to NORMAL
                if overall_score >= self.elevated_enter:
                    target_state = "ELEVATED"
                    st["recovery_started_at"] = None
                    st["recovery_start_time"] = None
                elif st["recovery_start_time"] and (now - st["recovery_start_time"]) >= self.recovery_duration_sec:
                    target_state = "NORMAL"
                    st["cleared_at"] = now_iso
                    st["recovery_started_at"] = None
                    st["recovery_start_time"] = None
                else:
                    target_state = "RECOVERING"

            else:  # NORMAL or OBSERVATION
                if overall_score >= self.critical_enter:
                    target_state = "CRITICAL"
                elif overall_score >= self.elevated_enter:
                    target_state = "ELEVATED"
                elif overall_score >= 0.30:
                    target_state = "EARLY_WARNING"
                elif overall_score >= 0.18:
                    target_state = "OBSERVATION"
                else:
                    target_state = "NORMAL"

        # Handle Transition events
        if target_state != prev_state:
            # Entering alert from normal
            if prev_state in ("NORMAL", "OBSERVATION") and target_state in ("EARLY_WARNING", "ELEVATED", "CRITICAL"):
                st["created_at"] = now_iso
                st["peak_score"] = overall_score
                st["active_domain"] = target_domain
                st["trigger_reason"] = reason
                st["active_alert_id"] = f"ALT-{datetime.datetime.utcnow().strftime('%H%M%S')}"

            # Entering recovering
            if target_state == "RECOVERING" and prev_state != "RECOVERING":
                st["recovery_started_at"] = now_iso
                st["recovery_start_time"] = now

            # Entering normal (fully cleared)
            if target_state == "NORMAL":
                st["active_alert_id"] = None
                st["peak_score"] = 0.0
                st["active_domain"] = None
                st["trigger_reason"] = "All parameters normal"

            # Record timeline event
            st["state_timeline"].append({
                "time": datetime.datetime.utcnow().strftime("%H:%M:%S"),
                "timestamp": now_iso,
                "from_state": prev_state,
                "to_state": target_state,
                "domain": target_domain,
                "reason": reason,
                "score": round(overall_score, 3),
            })

        st["current_state"] = target_state
        st["peak_score"] = max(st["peak_score"], overall_score)
        if target_state not in ("NORMAL", "RECOVERING"):
            st["active_domain"] = target_domain
            st["trigger_reason"] = reason

        # Calculate recovery progress percentage
        recovery_progress = 100
        if target_state == "RECOVERING" and st["recovery_start_time"]:
            elapsed = now - st["recovery_start_time"]
            recovery_progress = min(100, int((elapsed / self.recovery_duration_sec) * 100))

        return {
            "current_state": target_state,
            "previous_state": prev_state,
            "active_domain": st["active_domain"],
            "trigger_reason": st["trigger_reason"],
            "peak_score": round(st["peak_score"], 3),
            "current_score": round(st["current_score"], 3),
            "active_alert_id": st["active_alert_id"],
            "created_at": st["created_at"],
            "recovery_started_at": st["recovery_started_at"],
            "recovery_progress_pct": recovery_progress,
            "cleared_at": st["cleared_at"],
            "is_active_alert": target_state in ("ELEVATED", "CRITICAL"),
            "is_recovering": target_state == "RECOVERING",
            "is_normal": target_state == "NORMAL",
            "timeline": list(reversed(st["state_timeline"]))[:15],
        }

_alert_sm = AlertStateMachine()

def get_alert_state_machine() -> AlertStateMachine:
    return _alert_sm
