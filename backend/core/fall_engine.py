"""
VITALSYNC: Multi-Stage Fall & Immobility Detection Engine
Implements a temporal state machine for fall verification:
Impact Spike -> Orientation Change -> Post-Event Inactivity -> Fall Candidate -> Confirmation Window.
If movement resumes normally, the candidate is automatically CANCELLED.
If ADXL345 is invalid/disconnected, status is SENSOR_UNAVAILABLE, NEVER a false fall alert.
"""

import math
import time
import numpy as np
from typing import Dict, Any, Optional
from collections import deque

class FallDetectorState:
    def __init__(self, device_id: str):
        self.device_id = device_id
        # State: NORMAL, IMPACT_DETECTED, ORIENTATION_CHANGED, FALL_CANDIDATE, CONFIRMED_FALL, CANCELLED_RECOVERED
        self.state = "NORMAL"
        self.state_entered_time = time.time()
        self.recent_buffer = deque(maxlen=20)
        self.impact_time: Optional[float] = None
        self.candidate_entered_time: Optional[float] = None
        self.confirmation_window_sec = 6.0  # Time to monitor post-impact immobility
        self.impact_magnitude = 0.0
        self.orientation_tilt = 0.0
        self.post_inactivity_samples = 0
        self.recovery_movement_detected = False

    def reset_to_normal(self, reason: str = "Nominal movement"):
        self.state = "NORMAL"
        self.impact_time = None
        self.candidate_entered_time = None
        self.impact_magnitude = 0.0
        self.post_inactivity_samples = 0
        self.recovery_movement_detected = False

class FallEngine:
    def __init__(self):
        self._states: Dict[str, FallDetectorState] = {}

    def _get_state(self, device_id: str) -> FallDetectorState:
        if device_id not in self._states:
            self._states[device_id] = FallDetectorState(device_id)
        return self._states[device_id]

    def evaluate(
        self,
        device_id: str,
        ax: float,
        ay: float,
        az: float,
        sensor_valid: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes multi-stage temporal fall verification on incoming accelerometer vector.
        """
        # Rule: If sensor is invalid/disconnected, NEVER emit a fall!
        if not sensor_valid or ax is None or ay is None or az is None or math.isnan(ax):
            st = self._get_state(device_id)
            st.reset_to_normal()
            return {
                "fall_state": "SENSOR_UNAVAILABLE",
                "is_candidate": False,
                "is_confirmed": False,
                "confidence": 0.0,
                "message": "Activity sensor unavailable or disconnected. Fall detection suspended.",
            }

        mag = math.sqrt(ax**2 + ay**2 + az**2)
        horizontal_comp = math.sqrt(ax**2 + ay**2)
        st = self._get_state(device_id)
        now = time.time()

        st.recent_buffer.append({"mag": mag, "ax": ax, "ay": ay, "az": az, "time": now})
        
        # Calculate recent variance over last 6 samples
        recent_mags = [s["mag"] for s in list(st.recent_buffer)[-6:]]
        var = float(np.var(recent_mags)) if len(recent_mags) >= 3 else 0.01

        # STAGE 1 & 2: IMPACT & ORIENTATION CHANGE DETECTION
        if st.state in ("NORMAL", "CANCELLED_RECOVERED"):
            # A true fall impact requires high dynamic jerk (>2.4g or sharp horizontal impact)
            if mag > 2.45 or (horizontal_comp > 2.1 and abs(az) < 0.45):
                st.state = "IMPACT_DETECTED"
                st.impact_time = now
                st.impact_magnitude = mag
                st.orientation_tilt = horizontal_comp
                st.post_inactivity_samples = 0
                return {
                    "fall_state": "IMPACT_DETECTED",
                    "is_candidate": False,
                    "is_confirmed": False,
                    "confidence": 0.40,
                    "message": f"High acceleration event detected ({mag:.2f}g). Evaluating orientation and post-event motion.",
                }
            else:
                st.state = "NORMAL"
                return {
                    "fall_state": "NORMAL",
                    "is_candidate": False,
                    "is_confirmed": False,
                    "confidence": 0.95,
                    "message": "Normal motion dynamics.",
                }

        # STAGE 3: POST-IMPACT MONITORING
        if st.state == "IMPACT_DETECTED":
            elapsed_since_impact = now - (st.impact_time or now)
            
            # Check if person is upright (|az| >= 0.85g) or actively moving (mag > 1.20g)
            if abs(az) >= 0.85 or mag > 1.25:
                st.state = "CANCELLED_RECOVERED"
                return {
                    "fall_state": "CANCELLED_RECOVERED",
                    "is_candidate": False,
                    "is_confirmed": False,
                    "confidence": 0.92,
                    "message": "Upright posture / normal mobility continued after acceleration event. Fall candidate cancelled.",
                }

            # Lying down / tilted (|az| < 0.80g) and inactive
            st.post_inactivity_samples += 1
            st.state = "FALL_CANDIDATE"
            st.candidate_entered_time = now
            return {
                "fall_state": "FALL_CANDIDATE",
                "is_candidate": True,
                "is_confirmed": False,
                "confidence": 0.80,
                "message": "Possible fall detected: impact followed by persistent immobility and orientation shift. Monitoring confirmation window.",
            }

        # STAGE 4: FALL CANDIDATE CONFIRMATION WINDOW
        if st.state == "FALL_CANDIDATE":
            st.post_inactivity_samples += 1
            candidate_duration = now - (st.candidate_entered_time or now)
            
            # RECOVERY CHECK: If patient resumes active movement or upright posture
            if abs(az) >= 0.85 or mag > 1.20:
                st.state = "CANCELLED_RECOVERED"
                return {
                    "fall_state": "CANCELLED_RECOVERED",
                    "is_candidate": False,
                    "is_confirmed": False,
                    "confidence": 0.90,
                    "message": "Patient resumed active movement / upright posture. Fall candidate cancelled, alert cleared.",
                }

            # CONFIRMATION: If immobility persists past the confirmation window or 4 post-impact samples
            if candidate_duration >= st.confirmation_window_sec or st.post_inactivity_samples >= 4:
                st.state = "CONFIRMED_FALL"
                return {
                    "fall_state": "CONFIRMED_FALL",
                    "is_candidate": False,
                    "is_confirmed": True,
                    "confidence": 0.95,
                    "message": "Confirmed Fall Event: Severe impact followed by sustained immobility.",
                }

            return {
                "fall_state": "FALL_CANDIDATE",
                "is_candidate": True,
                "is_confirmed": False,
                "confidence": 0.80,
                "message": f"Fall candidate verification in progress ({candidate_duration:.1f}s / {st.confirmation_window_sec:.0f}s).",
            }

        # STAGE 5: CONFIRMED FALL
        if st.state == "CONFIRMED_FALL":
            # If patient stands up and walks normally again
            if mag > 1.35 and var > 0.10:
                st.state = "CANCELLED_RECOVERED"
                return {
                    "fall_state": "CANCELLED_RECOVERED",
                    "is_candidate": False,
                    "is_confirmed": False,
                    "confidence": 0.85,
                    "message": "Patient has resumed mobility. Fall event transitioning to recovered.",
                }
            return {
                "fall_state": "CONFIRMED_FALL",
                "is_candidate": False,
                "is_confirmed": True,
                "confidence": 0.95,
                "message": "CRITICAL: Patient immobile following fall event. Emergency assistance required.",
            }

        return {
            "fall_state": st.state,
            "is_candidate": False,
            "is_confirmed": False,
            "confidence": 0.85,
            "message": "Motion monitoring active.",
        }

_fall_engine = FallEngine()

def get_fall_engine() -> FallEngine:
    return _fall_engine
