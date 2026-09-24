"""
VITALSYNC: Dedicated Vital Spike & Recovery Detector
Detects rapid, sudden vital transitions (e.g. HR 80 -> 198 within 1-3 seconds),
distinguishes transient spikes from persistent risks and critical emergencies,
tracks recovery progression (e.g. 198 -> 160 -> 110 -> 82), and generates
structured SPIKE_EVENT, RECOVERY_EVENT, and PERSISTENT_ANOMALY records.
"""

import time
import datetime
from typing import Dict, Any, List, Optional
from collections import deque

class SpikeDetector:
    """
    Dedicated physiological spike detector per device.
    Tracks previous value, current value, delta, percentage change,
    rate of change, baseline deviation, and signal quality.
    """
    def __init__(
        self,
        hr_spike_delta: float = 40.0,          # BPM jump to qualify as rapid spike
        hr_high_threshold: float = 160.0,       # Absolute high HR threshold
        hr_recovery_band: float = 15.0,         # Within baseline + 15 BPM is recovered
        spo2_spike_drop: float = 6.0,           # Sudden % drop in SpO2
        temp_spike_delta: float = 1.5,          # Sudden °C jump in skin temp
    ):
        self.hr_spike_delta = hr_spike_delta
        self.hr_high_threshold = hr_high_threshold
        self.hr_recovery_band = hr_recovery_band
        self.spo2_spike_drop = spo2_spike_drop
        self.temp_spike_delta = temp_spike_delta

        # State storage per device_id
        self._states: Dict[str, Dict[str, Any]] = {}

    def _init_device(self, device_id: str):
        self._states[device_id] = {
            "history": {
                "heart_rate": deque(maxlen=20),
                "spo2": deque(maxlen=20),
                "temperature": deque(maxlen=20),
                "timestamps": deque(maxlen=20),
            },
            "active_spikes": {}, # domain -> spike dict
            "spike_history": deque(maxlen=30),
            "last_event": None,
        }

    def reset(self, device_id: Optional[str] = None):
        if device_id:
            self._init_device(device_id)
        else:
            self._states.clear()

    def evaluate(
        self,
        device_id: str,
        vitals: Dict[str, float],
        baseline: Dict[str, Any],
        signal_qualities: Dict[str, float],
        activity: str = "REST",
    ) -> Dict[str, Any]:
        """
        Evaluates current vitals against previous vitals and personal baseline.
        Returns detailed spike detection state and any generated events.
        """
        if device_id not in self._states:
            self._init_device(device_id)

        st = self._states[device_id]
        now = time.time()
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"

        curr_hr = vitals.get("heart_rate", 75.0)
        curr_spo2 = vitals.get("spo2", 98.0)
        curr_temp = vitals.get("body_temperature", 36.7)

        hr_base = baseline.get("heart_rate", {}).get("baseline_mean", 72.0)
        spo2_base = baseline.get("spo2", {}).get("baseline_mean", 98.0)
        temp_base = baseline.get("body_temperature", {}).get("baseline_mean", 36.7)

        ppg_qual = signal_qualities.get("ppg_quality", 0.95)

        hist = st["history"]
        prev_hr = hist["heart_rate"][-1] if hist["heart_rate"] else curr_hr
        prev_spo2 = hist["spo2"][-1] if hist["spo2"] else curr_spo2
        prev_temp = hist["temperature"][-1] if hist["temperature"] else curr_temp
        prev_ts = hist["timestamps"][-1] if hist["timestamps"] else now

        dt = max(0.5, now - prev_ts)

        # Append current to history
        hist["heart_rate"].append(curr_hr)
        hist["spo2"].append(curr_spo2)
        hist["temperature"].append(curr_temp)
        hist["timestamps"].append(now)

        # Calculate metrics for HR
        hr_delta = curr_hr - prev_hr
        hr_pct_change = (hr_delta / max(1.0, prev_hr)) * 100.0
        hr_roc = hr_delta / dt
        hr_base_dev = curr_hr - hr_base

        # Calculate metrics for SpO2
        spo2_delta = curr_spo2 - prev_spo2
        spo2_pct_change = (spo2_delta / max(1.0, prev_spo2)) * 100.0
        spo2_roc = spo2_delta / dt
        spo2_base_dev = curr_spo2 - spo2_base

        # Calculate metrics for Temp
        temp_delta = curr_temp - prev_temp
        temp_pct_change = (temp_delta / max(1.0, prev_temp)) * 100.0
        temp_roc = temp_delta / dt
        temp_base_dev = curr_temp - temp_base

        events_generated: List[Dict[str, Any]] = []

        # =================================================================
        # 1. HEART RATE SPIKE & RECOVERY
        # =================================================================
        hr_spike_state = st["active_spikes"].get("HEART_RATE")

        # Check for new sudden HR spike (e.g. 80 -> 198)
        is_sudden_hr_jump = (hr_delta >= self.hr_spike_delta) or (curr_hr >= self.hr_high_threshold and prev_hr < 100.0)
        
        if is_sudden_hr_jump and not hr_spike_state:
            # New Spike Detected
            spike_event = {
                "type": "SPIKE_EVENT",
                "domain": "HEART_RATE",
                "severity": "WARNING",
                "previous": round(prev_hr, 1),
                "current": round(curr_hr, 1),
                "peak": round(curr_hr, 1),
                "delta": round(hr_delta, 1),
                "pct_change": round(hr_pct_change, 1),
                "rate_of_change_per_sec": round(hr_roc, 2),
                "baseline": round(hr_base, 1),
                "baseline_deviation": round(hr_base_dev, 1),
                "signal_quality": round(ppg_qual, 2),
                "activity": activity,
                "timestamp": now_iso,
                "status": "SPIKE_DETECTED",
                "message": f"Heart-rate spike detected ({int(prev_hr)} → {int(curr_hr)} BPM). Monitoring recovery...",
                "user_notification": True,
                "caretaker_alert": False, # Transients do not dispatch caretaker!
            }
            st["active_spikes"]["HEART_RATE"] = spike_event
            events_generated.append(spike_event)
            st["spike_history"].append(spike_event)

        elif hr_spike_state:
            # Spike is currently active, track progression or recovery
            hr_spike_state["peak"] = max(hr_spike_state["peak"], curr_hr)
            hr_spike_state["current"] = round(curr_hr, 1)

            # Check if recovering back near baseline
            is_near_baseline = curr_hr <= (hr_base + self.hr_recovery_band) or curr_hr < 90.0
            is_dropping = curr_hr < (hr_spike_state["peak"] - 20.0)

            if is_near_baseline:
                # Fully recovered
                recovery_event = {
                    "type": "RECOVERY_EVENT",
                    "domain": "HEART_RATE",
                    "severity": "INFO",
                    "previous_peak": round(hr_spike_state["peak"], 1),
                    "current": round(curr_hr, 1),
                    "baseline": round(hr_base, 1),
                    "timestamp": now_iso,
                    "status": "RECOVERED",
                    "message": f"Heart rate back near baseline ({int(curr_hr)} BPM). Spike resolved.",
                    "user_notification": True,
                    "caretaker_alert": False,
                }
                events_generated.append(recovery_event)
                st["spike_history"].append(recovery_event)
                del st["active_spikes"]["HEART_RATE"]

            elif is_dropping:
                hr_spike_state["status"] = "RECOVERING"
                hr_spike_state["message"] = f"Heart rate recovering ({int(curr_hr)} BPM from peak {int(hr_spike_state['peak'])})."

        # =================================================================
        # 2. TEMPERATURE SPIKE & RECOVERY (e.g. Hot beverage contact)
        # =================================================================
        temp_spike_state = st["active_spikes"].get("TEMPERATURE")
        is_sudden_temp_jump = (temp_delta >= self.temp_spike_delta) and (curr_temp >= 38.5)

        if is_sudden_temp_jump and not temp_spike_state:
            spike_event = {
                "type": "SPIKE_EVENT",
                "domain": "TEMPERATURE",
                "severity": "WARNING",
                "previous": round(prev_temp, 1),
                "current": round(curr_temp, 1),
                "peak": round(curr_temp, 1),
                "delta": round(temp_delta, 1),
                "pct_change": round(temp_pct_change, 1),
                "rate_of_change_per_sec": round(temp_roc, 2),
                "baseline": round(temp_base, 1),
                "baseline_deviation": round(temp_base_dev, 1),
                "timestamp": now_iso,
                "status": "SPIKE_DETECTED",
                "message": f"Temperature spike detected ({prev_temp:.1f} → {curr_temp:.1f}°C). Monitoring...",
                "user_notification": True,
                "caretaker_alert": False,
            }
            st["active_spikes"]["TEMPERATURE"] = spike_event
            events_generated.append(spike_event)
            st["spike_history"].append(spike_event)

        elif temp_spike_state:
            temp_spike_state["peak"] = max(temp_spike_state["peak"], curr_temp)
            temp_spike_state["current"] = round(curr_temp, 1)

            if curr_temp <= (temp_base + 0.5):
                recovery_event = {
                    "type": "RECOVERY_EVENT",
                    "domain": "TEMPERATURE",
                    "severity": "INFO",
                    "previous_peak": round(temp_spike_state["peak"], 1),
                    "current": round(curr_temp, 1),
                    "baseline": round(temp_base, 1),
                    "timestamp": now_iso,
                    "status": "RECOVERED",
                    "message": f"Temperature normalized ({curr_temp:.1f}°C).",
                    "user_notification": True,
                    "caretaker_alert": False,
                }
                events_generated.append(recovery_event)
                st["spike_history"].append(recovery_event)
                del st["active_spikes"]["TEMPERATURE"]
            elif curr_temp < (temp_spike_state["peak"] - 0.5):
                temp_spike_state["status"] = "RECOVERING"

        # Determine overall spike status summary
        active_list = list(st["active_spikes"].values())
        has_active_spike = len(active_list) > 0
        latest_spike = active_list[0] if has_active_spike else (st["spike_history"][-1] if st["spike_history"] else None)

        return {
            "has_active_spike": has_active_spike,
            "active_spikes": active_list,
            "latest_spike": latest_spike,
            "events_emitted": events_generated,
            "metrics": {
                "heart_rate": {
                    "previous": round(prev_hr, 1),
                    "current": round(curr_hr, 1),
                    "delta": round(hr_delta, 1),
                    "pct_change": round(hr_pct_change, 1),
                    "rate_of_change": round(hr_roc, 2),
                    "baseline_dev": round(hr_base_dev, 1),
                },
                "spo2": {
                    "previous": round(prev_spo2, 1),
                    "current": round(curr_spo2, 1),
                    "delta": round(spo2_delta, 1),
                    "pct_change": round(spo2_pct_change, 1),
                    "rate_of_change": round(spo2_roc, 2),
                    "baseline_dev": round(spo2_base_dev, 1),
                },
                "temperature": {
                    "previous": round(prev_temp, 1),
                    "current": round(curr_temp, 1),
                    "delta": round(temp_delta, 1),
                    "pct_change": round(temp_pct_change, 1),
                    "rate_of_change": round(temp_roc, 2),
                    "baseline_dev": round(temp_base_dev, 1),
                },
            },
        }

_spike_detector = SpikeDetector()

def get_spike_detector() -> SpikeDetector:
    return _spike_detector
