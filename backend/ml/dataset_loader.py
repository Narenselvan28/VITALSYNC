"""
AAROGYA-SHIELD: Dataset Loader
Loads and processes clinical physiological data from PhysioNet BIDMC PPG and Respiration Dataset,
synthesizes complementary multi-modal wearable signals (activity, ambient temperature, humidity,
MQ-45 environmental indicator, body temperature) to train edge-AI models with clinical foundation.
"""

import os
import glob
import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any

# Path to the BIDMC dataset in workspace
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIDMC_NUMERICS_PATH = os.path.join(
    BASE_DIR, "Datasets", "bidmc-ppg-and-respiration-dataset-1.0.0", "bidmc_csv"
)

def load_bidmc_numerics() -> pd.DataFrame:
    """
    Loads all available BIDMC numerics CSV files containing:
    Time [s], HR, PULSE, RESP, SpO2
    Extracts second-by-second physiological metrics across 53 patients.
    """
    records = []
    csv_files = sorted(glob.glob(os.path.join(BIDMC_NUMERICS_PATH, "bidmc_*_Numerics.csv")))
    
    if not csv_files:
        print(f"[Warning] No BIDMC CSV files found at {BIDMC_NUMERICS_PATH}. Generating synthetic clinical seed.")
        return generate_synthetic_clinical_seed()

    for file_path in csv_files:
        subject_id = os.path.basename(file_path).split("_")[1]
        try:
            df = pd.read_csv(file_path)
            # Standardize column names (strip whitespace)
            df.columns = [c.strip() for c in df.columns]
            
            # Filter valid readings
            if "HR" in df.columns and "SpO2" in df.columns:
                df["subject_id"] = f"SUBJ_{subject_id}"
                # Clean invalid/missing markers (BIDMC uses 0 or NaN for missing)
                df = df[(df["HR"] > 30) & (df["HR"] < 220) & (df["SpO2"] > 60) & (df["SpO2"] <= 100)]
                records.append(df)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            continue

    if not records:
        return generate_synthetic_clinical_seed()

    combined_df = pd.concat(records, ignore_index=True)
    print(f"[DatasetLoader] Successfully loaded {len(combined_df)} clinical data points across {len(records)} subjects from BIDMC.")
    return combined_df


def generate_synthetic_clinical_seed(n_samples: int = 15000) -> pd.DataFrame:
    """Fallback generator based on real clinical physiological distributions."""
    np.random.seed(42)
    hr = np.random.normal(76, 12, n_samples).clip(45, 180)
    spo2 = np.random.normal(97.5, 1.8, n_samples).clip(75, 100)
    resp = np.random.normal(16, 3.5, n_samples).clip(8, 40)
    return pd.DataFrame({
        "Time [s]": np.arange(n_samples),
        "HR": hr,
        "PULSE": hr + np.random.normal(0, 1, n_samples),
        "RESP": resp,
        "SpO2": spo2,
        "subject_id": "SYNTH_01"
    })


def create_multimodal_training_dataset() -> pd.DataFrame:
    """
    Creates a rich multi-modal dataset combining:
    1. Clinical ground-truth HR, SpO2, Resp from BIDMC
    2. Wearable ADXL345 accelerometer data & Activity states:
       - REST (0): static low variance
       - LIGHT (1): low movement (walking/sitting)
       - MODERATE (2): continuous motion
       - HIGH (3): intense movement / running
       - FALL-CANDIDATE (4): sudden high jerk spike followed by inactivity
    3. Body temperature (°C) normal: 36.5-37.2, fever/heat stress: 37.8-40.5
    4. Ambient temperature (°C) and humidity (%)
    5. MQ-45 Environmental Air Quality index (exposure signal 0-1000)
    6. Personal Baseline relative deviations
    7. Multi-target ground truths for:
       - general_anomaly (0 or 1)
       - respiratory_risk (0=LOW, 1=EARLY_WARNING, 2=ELEVATED, 3=CRITICAL)
       - heat_stress_risk (0=LOW, 1=EARLY_WARNING, 2=ELEVATED, 3=CRITICAL)
       - environmental_risk (0=LOW, 1=EARLY_WARNING, 2=ELEVATED, 3=CRITICAL)
    """
    base_df = load_bidmc_numerics()
    np.random.seed(42)
    n = len(base_df)

    # Subsample if too large or augment if needed for balanced scenarios
    # Target ~20,000 samples for clean fast edge training
    if n > 25000:
        base_df = base_df.sample(25000, random_state=42).reset_index(drop=True)
        n = len(base_df)

    hr = base_df["HR"].values.astype(float)
    spo2 = base_df["SpO2"].values.astype(float)
    resp = base_df["RESP"].values.astype(float) if "RESP" in base_df.columns else np.random.normal(16, 3, n)

    # Calculate simulated personal baselines for each subject or cluster
    # Personal baseline HR ~ 72 +/- 8, SpO2 ~ 98 +/- 1, Body Temp ~ 36.8
    subj_baseline_hr = np.random.normal(74, 6, n)
    subj_baseline_spo2 = np.random.normal(98, 0.8, n)
    subj_baseline_temp = np.random.normal(36.7, 0.25, n)

    # Ambient conditions
    ambient_temp = np.random.uniform(22, 38, n)
    ambient_humidity = np.random.uniform(30, 85, n)
    
    # Body temperature correlates with ambient heat, activity, and infection/inflammation
    body_temp = subj_baseline_temp + np.random.normal(0, 0.2, n)
    
    # MQ-45 Environmental exposure indicator (baseline ~ 150-350, polluted ~ 500-1000)
    mq45 = np.random.exponential(180, n) + 120
    mq45 = np.clip(mq45, 50, 950)

    # ADXL345 Accelerometer & Activity state
    # 0: REST, 1: LIGHT, 2: MODERATE, 3: HIGH, 4: FALL-CANDIDATE
    activity_states = np.random.choice([0, 1, 2, 3, 4], size=n, p=[0.45, 0.35, 0.12, 0.06, 0.02])
    
    accel_x = np.zeros(n)
    accel_y = np.zeros(n)
    accel_z = np.ones(n) # ~1g gravity on Z at rest

    for i in range(n):
        act = activity_states[i]
        if act == 0:  # REST
            accel_x[i] = np.random.normal(0.0, 0.05)
            accel_y[i] = np.random.normal(0.0, 0.05)
            accel_z[i] = np.random.normal(1.0, 0.05)
        elif act == 1:  # LIGHT
            accel_x[i] = np.random.normal(0.1, 0.15)
            accel_y[i] = np.random.normal(0.1, 0.15)
            accel_z[i] = np.random.normal(0.95, 0.15)
        elif act == 2:  # MODERATE
            accel_x[i] = np.random.normal(0.3, 0.3)
            accel_y[i] = np.random.normal(0.3, 0.3)
            accel_z[i] = np.random.normal(1.1, 0.3)
        elif act == 3:  # HIGH
            accel_x[i] = np.random.normal(0.6, 0.5)
            accel_y[i] = np.random.normal(0.6, 0.5)
            accel_z[i] = np.random.normal(1.4, 0.5)
        elif act == 4:  # FALL-CANDIDATE
            accel_x[i] = np.random.uniform(1.8, 3.2) * np.random.choice([-1, 1])
            accel_y[i] = np.random.uniform(1.5, 3.0) * np.random.choice([-1, 1])
            accel_z[i] = np.random.uniform(0.1, 0.4)

    # Accelerometer Magnitude (SVM)
    accel_mag = np.sqrt(accel_x**2 + accel_y**2 + accel_z**2)
    
    # PPG signal quality (0 to 1) - higher motion typically degrades PPG quality
    ppg_quality = np.clip(1.0 - (accel_mag - 1.0).clip(0, 2) * 0.3 + np.random.normal(0, 0.05, n), 0.2, 1.0)

    # Inject targeted physiological scenarios to ensure robust multi-class representation:
    # 1. Heat-stress scenario: ambient_temp > 35°C, humidity > 70%, body_temp > 38.0°C, elevated HR
    heat_idx = np.random.choice(n, size=int(n * 0.10), replace=False)
    ambient_temp[heat_idx] += np.random.uniform(6, 12, len(heat_idx))
    ambient_humidity[heat_idx] += np.random.uniform(15, 30, len(heat_idx))
    ambient_temp = np.clip(ambient_temp, 15, 48)
    ambient_humidity = np.clip(ambient_humidity, 20, 99)
    body_temp[heat_idx] += np.random.uniform(1.0, 2.8, len(heat_idx))
    hr[heat_idx] += np.random.uniform(15, 35, len(heat_idx))

    # 2. Respiratory distress scenario: SpO2 drops, HR increases, Resp increases
    resp_idx = np.random.choice(n, size=int(n * 0.12), replace=False)
    spo2[resp_idx] -= np.random.uniform(4, 14, len(resp_idx))
    hr[resp_idx] += np.random.uniform(10, 30, len(resp_idx))
    resp[resp_idx] += np.random.uniform(6, 16, len(resp_idx))

    # 3. High environmental exposure scenario: MQ-45 spikes, combined with mild respiratory reaction
    env_idx = np.random.choice(n, size=int(n * 0.10), replace=False)
    mq45[env_idx] = np.random.uniform(500, 950, len(env_idx))
    spo2[env_idx] -= np.random.uniform(1, 3, len(env_idx))

    # Clip all physiological signals to realistic biological boundaries
    hr = np.clip(hr, 40, 200)
    spo2 = np.clip(spo2, 70, 100)
    body_temp = np.clip(body_temp, 35.0, 42.0)

    # Feature Engineering: Deviations from Personal Baseline
    hr_deviation = (hr - subj_baseline_hr) / subj_baseline_hr
    spo2_deviation = (spo2 - subj_baseline_spo2) / subj_baseline_spo2
    temp_deviation = (body_temp - subj_baseline_temp)

    # Heat Index estimation (Rothfusz equation approximation)
    heat_index = (
        -8.78469475556
        + 1.61139411 * ambient_temp
        + 2.33854883889 * ambient_humidity
        - 0.14611605 * ambient_temp * ambient_humidity
        - 0.012308094 * (ambient_temp ** 2)
        - 0.0164248277778 * (ambient_humidity ** 2)
        + 0.002211732 * (ambient_temp ** 2) * ambient_humidity
        + 0.00072546 * ambient_temp * (ambient_humidity ** 2)
        - 0.000003582 * (ambient_temp ** 2) * (ambient_humidity ** 2)
    )

    # Construct Ground Truth Labels based on clinical and physiological guidelines:
    # 0 = LOW, 1 = EARLY_WARNING, 2 = ELEVATED, 3 = CRITICAL

    # Respiratory Risk Model target
    respiratory_risk = np.zeros(n, dtype=int)
    for i in range(n):
        # SpO2 deviation, HR increase, and MQ-45 exposure
        s = spo2[i]
        s_dev = spo2_deviation[i]
        h_dev = hr_deviation[i]
        if s < 88 or s_dev < -0.10:
            respiratory_risk[i] = 3  # CRITICAL
        elif s < 92 or (s_dev < -0.06 and h_dev > 0.15):
            respiratory_risk[i] = 2  # ELEVATED
        elif s < 95 or s_dev < -0.03 or (s_dev < -0.02 and mq45[i] > 450):
            respiratory_risk[i] = 1  # EARLY_WARNING
        else:
            respiratory_risk[i] = 0  # LOW

    # Heat Stress Risk Model target
    heat_stress_risk = np.zeros(n, dtype=int)
    for i in range(n):
        bt = body_temp[i]
        hi = heat_index[i]
        if bt > 39.5 or (hi > 48 and bt > 38.5):
            heat_stress_risk[i] = 3  # CRITICAL
        elif bt > 38.5 or (hi > 42 and bt > 37.8):
            heat_stress_risk[i] = 2  # ELEVATED
        elif bt > 37.6 or hi > 38 or (hi > 35 and hr_deviation[i] > 0.15):
            heat_stress_risk[i] = 1  # EARLY_WARNING
        else:
            heat_stress_risk[i] = 0  # LOW

    # Environmental Exposure Risk Model target
    environmental_risk = np.zeros(n, dtype=int)
    for i in range(n):
        gas = mq45[i]
        if gas > 700:
            environmental_risk[i] = 3  # CRITICAL
        elif gas > 450:
            environmental_risk[i] = 2  # ELEVATED
        elif gas > 280:
            environmental_risk[i] = 1  # EARLY_WARNING
        else:
            environmental_risk[i] = 0  # LOW

    # General Anomaly target (binary: 0 normal, 1 anomalous)
    general_anomaly = (
        (respiratory_risk >= 2) |
        (heat_stress_risk >= 2) |
        (environmental_risk >= 2) |
        (activity_states == 4) |
        (spo2 < 91) |
        (hr > 140) |
        (hr < 48)
    ).astype(int)

    # Assemble comprehensive DataFrame
    df = pd.DataFrame({
        "heart_rate": hr,
        "spo2": spo2,
        "ppg_quality": ppg_quality,
        "body_temperature": body_temp,
        "ambient_temperature": ambient_temp,
        "humidity": ambient_humidity,
        "heat_index": heat_index,
        "accel_x": accel_x,
        "accel_y": accel_y,
        "accel_z": accel_z,
        "accel_mag": accel_mag,
        "mq45": mq45,
        "activity_state": activity_states,
        "baseline_hr": subj_baseline_hr,
        "baseline_spo2": subj_baseline_spo2,
        "baseline_temp": subj_baseline_temp,
        "hr_deviation": hr_deviation,
        "spo2_deviation": spo2_deviation,
        "temp_deviation": temp_deviation,
        "general_anomaly": general_anomaly,
        "respiratory_risk": respiratory_risk,
        "heat_stress_risk": heat_stress_risk,
        "environmental_risk": environmental_risk,
    })

    return df

if __name__ == "__main__":
    df = create_multimodal_training_dataset()
    print("Dataset generation complete. Shape:", df.shape)
    print("Class distributions:")
    print("General Anomaly:", df["general_anomaly"].value_counts().to_dict())
    print("Respiratory Risk:", df["respiratory_risk"].value_counts().to_dict())
    print("Heat Stress Risk:", df["heat_stress_risk"].value_counts().to_dict())
    print("Environmental Risk:", df["environmental_risk"].value_counts().to_dict())
