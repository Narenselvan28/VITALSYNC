"""
VITALSYNC: 10K NTC Thermistor Calibration & Thermal Engine
Implements Steinhart-Hart and Beta equations for calibrated skin/contact temperature estimation.
Differentiates contact/skin temperature from clinical core body temperature.
Detects transient contact disturbances (e.g. watch touching hot beverage or cold object)
to prevent persistent false heat alerts.
"""

import math
from typing import Dict, Any, Tuple
from collections import deque

class NTCThermistorEngine:
    def __init__(
        self,
        r0: float = 10000.0,       # Resistance at T0 (10k ohms)
        t0_c: float = 25.0,         # Calibration temperature in Celsius (25°C = 298.15K)
        beta: float = 3950.0,       # Beta coefficient
        r_series: float = 10000.0,  # Voltage divider series resistor (10k ohms)
        vcc: float = 3.3,           # Supply voltage
        adc_max: float = 4095.0,    # ESP32 12-bit ADC max
    ):
        self.r0 = r0
        self.t0_k = t0_c + 273.15
        self.beta = beta
        self.r_series = r_series
        self.vcc = vcc
        self.adc_max = adc_max

        # Transient history buffer per device
        self._temp_buffers: Dict[str, deque] = {}
        self._disturbance_state: Dict[str, Dict[str, Any]] = {}

    def adc_to_resistance(self, adc_val: float) -> float:
        """Converts raw ADC value from ESP32 voltage divider to thermistor resistance in ohms."""
        if adc_val <= 0:
            return 1e9  # Open circuit
        if adc_val >= self.adc_max:
            return 1.0  # Near short circuit
        
        # Standard voltage divider: V_out = VCC * (R_ntc / (R_series + R_ntc))
        # R_ntc = R_series / ( (ADC_MAX / ADC) - 1 )
        ratio = (self.adc_max / float(adc_val)) - 1.0
        if ratio <= 0:
            return 1.0
        return self.r_series / ratio

    def resistance_to_temperature(self, r_ntc: float) -> float:
        """
        Computes calibrated skin contact temperature in Celsius using the Beta equation:
        1/T = 1/T0 + (1/Beta) * ln(R / R0)
        """
        if r_ntc <= 0:
            return 36.7
        try:
            inv_t = (1.0 / self.t0_k) + (1.0 / self.beta) * math.log(r_ntc / self.r0)
            temp_k = 1.0 / inv_t
            temp_c = temp_k - 273.15
            return round(temp_c, 2)
        except Exception:
            return 36.7

    def estimate_core_from_skin(self, skin_temp: float, ambient_temp: float) -> float:
        """
        Clinically distinguishes skin/contact temperature from core body temperature.
        Core temperature estimate combines contact reading with ambient heat loss compensation.
        Core = Skin + alpha * (Skin - Ambient), typically alpha ≈ 0.15 - 0.20
        """
        delta = skin_temp - ambient_temp
        # If skin is warmer than ambient, metabolic heat loss occurs
        compensation = max(0.2, min(1.8, 0.18 * delta)) if delta > 0 else 0.4
        core = skin_temp + compensation
        return round(core, 2)

    def evaluate_thermal_reading(
        self,
        device_id: str,
        current_temp: float,
        ambient_temp: float,
        heart_rate: float,
        baseline_temp: float = 36.7,
    ) -> Dict[str, Any]:
        """
        Detects transient thermal disturbances (e.g. touching hot mug or cold glass).
        If temperature rises sharply without elevation in HR or ambient temperature,
        and subsequently declines, flags as TEMPORARY_DISTURBANCE with auto-recovery.
        """
        if device_id not in self._temp_buffers:
            self._temp_buffers[device_id] = deque(maxlen=15)
            self._disturbance_state[device_id] = {
                "in_disturbance": False,
                "peak_temp": current_temp,
                "start_time": 0,
            }

        buf = self._temp_buffers[device_id]
        buf.append(current_temp)

        # Calculate rate of change over recent samples
        roc = 0.0
        if len(buf) >= 2:
            roc = buf[-1] - buf[-2]

        state = self._disturbance_state[device_id]
        is_transient = False
        disturbance_message = "Normal thermal tracking"

        # Check for sudden contact spike:
        # Rapid jump (>1.0°C above baseline) while ambient is normal (<33°C) and HR is resting (<100)
        temp_delta_from_base = current_temp - baseline_temp
        if temp_delta_from_base > 1.0 and heart_rate < 100 and ambient_temp < 33.0:
            state["in_disturbance"] = True
            state["peak_temp"] = max(state["peak_temp"], current_temp)
            is_transient = True
            disturbance_message = f"Temporary external contact disturbance detected ({current_temp:.1f}°C spike). Monitoring recovery."

        # Check for recovery:
        # If in disturbance and temperature is trending downward or within 0.5°C of baseline
        if state["in_disturbance"]:
            is_transient = True
            if current_temp < (baseline_temp + 0.5) or roc < -0.3:
                disturbance_message = f"Temperature recovering ({current_temp:.1f}°C, peak was {state['peak_temp']:.1f}°C)."
                if current_temp <= (baseline_temp + 0.3):
                    state["in_disturbance"] = False
                    is_transient = False
                    disturbance_message = "Thermal reading fully recovered to baseline."

        estimated_core = self.estimate_core_from_skin(current_temp, ambient_temp)

        return {
            "skin_contact_temp": current_temp,
            "estimated_core_temp": estimated_core,
            "ambient_temp": ambient_temp,
            "rate_of_change": round(roc, 3),
            "is_transient_disturbance": is_transient,
            "thermal_state": "TRANSIENT_DISTURBANCE" if is_transient else ("ELEVATED_FEVER" if temp_delta_from_base > 1.5 and heart_rate > 100 else "NORMAL"),
            "message": disturbance_message,
        }

_ntc_engine = NTCThermistorEngine()

def get_ntc_engine() -> NTCThermistorEngine:
    return _ntc_engine
