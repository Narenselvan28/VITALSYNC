"""
VITALSYNC: Signal Processing & Noise Filtering Module
Implements median filtering, Exponential Moving Average (EMA),
rate-of-change computation, and transient spike filtering to remove high-frequency noise.
"""

import math
import numpy as np
from typing import Dict, Any, List, Optional
from collections import deque

class SignalProcessor:
    def __init__(self, window_size: int = 10, ema_alpha: float = 0.35):
        self.window_size = window_size
        self.ema_alpha = ema_alpha
        self._buffers: Dict[str, Dict[str, deque]] = {}
        self._ema_values: Dict[str, Dict[str, float]] = {}

    def _get_buffer(self, device_id: str, param: str) -> deque:
        if device_id not in self._buffers:
            self._buffers[device_id] = {}
        if param not in self._buffers[device_id]:
            self._buffers[device_id][param] = deque(maxlen=self.window_size)
        return self._buffers[device_id][param]

    def update_and_filter(self, device_id: str, param: str, raw_val: float) -> Dict[str, float]:
        """
        Processes a raw sensor sample:
        - median filter (rejects single outliers)
        - exponential moving average (EMA smoothed)
        - rate of change (derivative per sample)
        - transient delta
        """
        buf = self._get_buffer(device_id, param)
        buf.append(raw_val)

        # Median filter
        sorted_vals = sorted(list(buf))
        mid = len(sorted_vals) // 2
        median_val = sorted_vals[mid]

        # EMA smoothing
        if device_id not in self._ema_values:
            self._ema_values[device_id] = {}
        if param not in self._ema_values[device_id]:
            self._ema_values[device_id][param] = raw_val
        else:
            prev_ema = self._ema_values[device_id][param]
            self._ema_values[device_id][param] = (self.ema_alpha * raw_val) + ((1.0 - self.ema_alpha) * prev_ema)

        ema_val = self._ema_values[device_id][param]

        # Rate of change over last 3-5 samples
        roc = 0.0
        if len(buf) >= 2:
            roc = buf[-1] - buf[-2]

        # Transient spike detector: difference between raw sample and current smoothed EMA
        is_spike = abs(raw_val - ema_val) > (raw_val * 0.20 if raw_val > 50 else 3.0)

        return {
            "raw": round(raw_val, 2),
            "median": round(median_val, 2),
            "ema": round(ema_val, 2),
            "roc": round(roc, 3),
            "is_transient_spike": is_spike,
        }

    def detect_transient_spike_sequence(self, device_id: str, param: str, threshold_delta: float) -> bool:
        """
        Detects if recent samples represent a short spike:
        e.g. 72 -> 198 -> 75 (spikes up then returns back toward baseline)
        """
        buf = self._get_buffer(device_id, param)
        if len(buf) < 3:
            return False
        vals = list(buf)
        p0, p1, p2 = vals[-3], vals[-2], vals[-1]
        
        # Check if middle value peaked significantly and returned
        if (p1 - p0) > threshold_delta and (p1 - p2) > (threshold_delta * 0.7):
            return True
        return False

_signal_processor = SignalProcessor()

def get_signal_processor() -> SignalProcessor:
    return _signal_processor
