"""
VITALSYNC: Activity Classification & Actigraphy Engine
Processes ADXL345 3-axis accelerometer data into Signal Vector Magnitude (SVM),
jerk, movement variance, and temporal actigraphy states.
Prevents normal arm movements, walking, running, or wrist gestures from becoming false falls.
"""

import math
import numpy as np
from typing import Dict, Any, Tuple
from collections import deque

ACTIVITY_LABELS = {
    0: "REST",
    1: "SITTING",
    2: "STANDING",
    3: "WALKING",
    4: "RUNNING_HIGH_ACTIVITY",
    5: "HAND_MOVEMENT",
    6: "FALL_CANDIDATE",
    7: "UNKNOWN",
}

class ActivityEngine:
    def __init__(self, window_size: int = 15):
        self.window_size = window_size
        self._buffers: Dict[str, deque] = {}

    def _get_buffer(self, device_id: str) -> deque:
        if device_id not in self._buffers:
            self._buffers[device_id] = deque(maxlen=self.window_size)
        return self._buffers[device_id]

    def process_motion(
        self,
        device_id: str,
        ax: float,
        ay: float,
        az: float,
        sensor_valid: bool = True,
    ) -> Dict[str, Any]:
        """
        Calculates motion dynamics and classifies continuous activity.
        Handles sensor disconnection gracefully.
        """
        if not sensor_valid or ax is None or ay is None or az is None:
            return {
                "magnitude": 0.0,
                "horizontal_tilt": 0.0,
                "jerk": 0.0,
                "variance": 0.0,
                "activity_code": 7,
                "activity_state": "SENSOR_UNAVAILABLE",
                "intensity": "NONE",
                "is_active": False,
                "is_rest": False,
            }

        mag = math.sqrt(ax**2 + ay**2 + az**2)
        buf = self._get_buffer(device_id)
        
        # Calculate jerk relative to previous sample
        prev_mag = buf[-1]["mag"] if buf else 1.0
        jerk = abs(mag - prev_mag)

        # Store sample
        buf.append({
            "ax": ax,
            "ay": ay,
            "az": az,
            "mag": mag,
            "jerk": jerk,
        })

        # Calculate rolling variance over window
        mags = [s["mag"] for s in buf]
        variance = float(np.var(mags)) if len(mags) >= 3 else 0.005

        # Horizontal component (tilt/posture indicator)
        horizontal_comp = math.sqrt(ax**2 + ay**2)

        # Classification logic based on validated actigraphy cutoffs:
        if mag > 1.55 or variance > 0.25:
            code = 4
            state = "RUNNING_HIGH_ACTIVITY"
            intensity = "HIGH"
        elif (1.15 <= mag <= 1.55) and (variance > 0.035 or len(buf) < 3 or mag >= 1.22):
            code = 3
            state = "WALKING"
            intensity = "MODERATE"
        elif jerk > 0.35 and variance < 0.05:
            # Isolated wrist turning / arm gesture without whole-body rhythm
            code = 5
            state = "HAND_MOVEMENT"
            intensity = "LOW"
        elif variance > 0.015:
            code = 2
            state = "STANDING"
            intensity = "LIGHT"
        elif horizontal_comp > 0.3 and abs(az) < 0.95:
            code = 1
            state = "SITTING"
            intensity = "SEDENTARY"
        else:
            code = 0
            state = "REST"
            intensity = "REST"

        return {
            "magnitude": round(mag, 3),
            "horizontal_tilt": round(horizontal_comp, 3),
            "jerk": round(jerk, 3),
            "variance": round(variance, 4),
            "activity_code": code,
            "activity_state": state,
            "intensity": intensity,
            "is_active": code in (3, 4),
            "is_rest": code in (0, 1),
        }

_activity_engine = ActivityEngine()

def get_activity_engine() -> ActivityEngine:
    return _activity_engine
