"""
AAROGYA-SHIELD: ESP32 Hardware Emulator Daemon
Simulates the physical ESP32 IoT wearable transmitting sensor packets
via HTTP POST to /api/sensors/readings at 1 Hz.
Used to demonstrate and test "IoT LIVE MODE" without physical hardware attached.
"""

import sys
import time
import json
import random
import argparse
import requests
import datetime

DEFAULT_URL = "http://127.0.0.1:8000/api/sensors/readings"
DEVICE_ID = "ESP32-001"

def run_emulator(target_url: str = DEFAULT_URL, interval: float = 1.0, scenario: str = "normal", max_samples: int = 0):
    print("=" * 65)
    print(f"  AAROGYA-SHIELD: ESP32 HARDWARE EMULATOR")
    print(f"  Device ID: {DEVICE_ID}")
    print(f"  Target Endpoint: {target_url}")
    print(f"  Transmission Frequency: {1.0 / interval:.1f} Hz (Interval: {interval}s)")
    print(f"  Scenario: {scenario.upper()}")
    print("=" * 65)

    count = 0
    while True:
        count += 1
        ts = datetime.datetime.utcnow().isoformat() + "Z"

        # Baseline nominal parameters
        hr = 74.0 + random.uniform(-2, 3)
        spo2 = 98.0 + random.uniform(-0.5, 0.5)
        ppg_q = 0.95 + random.uniform(-0.02, 0.02)
        body_temp = 36.75 + random.uniform(-0.1, 0.1)
        amb_temp = 29.2 + random.uniform(-0.2, 0.2)
        humidity = 62.0 + random.uniform(-1, 1)
        ax = 0.02 + random.uniform(-0.01, 0.01)
        ay = 0.01 + random.uniform(-0.01, 0.01)
        az = 0.98 + random.uniform(-0.01, 0.01)
        mq45 = 185.0 + random.uniform(-15, 15)

        # Scenario overrides
        if scenario == "respiratory":
            # Progressive SpO2 drop and HR compensation
            spo2 = max(87.0, 97.0 - (count * 0.4))
            hr = min(118.0, 75.0 + (count * 1.5))
            mq45 = 380.0
        elif scenario == "heat_stress":
            amb_temp = min(44.0, 32.0 + (count * 0.4))
            humidity = min(88.0, 65.0 + (count * 0.8))
            body_temp = min(39.4, 37.0 + (count * 0.08))
            hr = min(125.0, 78.0 + (count * 1.6))
        elif scenario == "environmental":
            mq45 = min(850.0, 200.0 + (count * 30.0))
            spo2 = max(94.0, 98.0 - (count * 0.15))
        elif scenario == "fall":
            if count == 3:
                # Sudden high impact
                ax, ay, az = 2.4, 2.1, 0.2
            elif count > 3:
                # Inactive after fall
                ax, ay, az = 0.0, 0.0, 0.0
                hr = 98.0

        payload = {
            "device_id": DEVICE_ID,
            "timestamp": ts,
            "heart_rate": round(hr, 1),
            "spo2": round(spo2, 1),
            "ppg_quality": round(ppg_q, 2),
            "body_temperature": round(body_temp, 2),
            "ambient_temperature": round(amb_temp, 1),
            "humidity": round(humidity, 1),
            "accel_x": round(ax, 3),
            "accel_y": round(ay, 3),
            "accel_z": round(az, 3),
            "mq45": round(mq45, 0),
            "latitude": 10.662,
            "longitude": 76.891,
            "is_simulator": False,
        }

        try:
            resp = requests.post(target_url, json=payload, timeout=2.0)
            if resp.status_code == 200:
                res_json = resp.json()
                esc = res_json.get("escalation", {})
                level = esc.get("escalated_level", "UNKNOWN")
                print(f"[{count:03d}] Sent: HR={payload['heart_rate']} SpO2={payload['spo2']}% Temp={payload['body_temperature']}C MQ45={int(payload['mq45'])} -> Status: HTTP {resp.status_code} | Escalated Risk: {level}")
            else:
                print(f"[{count:03d}] Error: HTTP {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"[{count:03d}] Connection failed ({e})")

        if max_samples and count >= max_samples:
            print(f"[Done] Reached {max_samples} samples.")
            break

        time.sleep(interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ESP32 Hardware Emulator for AAROGYA-SHIELD")
    parser.add_argument("--url", default=DEFAULT_URL, help="Target API endpoint")
    parser.add_argument("--interval", type=float, default=1.0, help="Transmission interval in seconds")
    parser.add_argument("--scenario", choices=["normal", "respiratory", "heat_stress", "environmental", "fall"], default="normal", help="Simulation scenario")
    parser.add_argument("--samples", type=int, default=0, help="Number of samples to send (0 = infinite)")
    args = parser.parse_args()

    run_emulator(target_url=args.url, interval=args.interval, scenario=args.scenario, max_samples=args.samples)
