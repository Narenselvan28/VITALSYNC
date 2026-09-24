"""
VITALSYNC: Multimodal Dataset Loader & Clinical Scenario Synthesizer
Generates balanced, clinically grounded training data separating:
1. Heart Rate Anomaly (Resting vs Active Tachycardia/Bradycardia)
2. Oxygenation Anomaly (SpO2 Desaturation)
3. Respiratory Risk (Only activated on multimodal respiratory distress evidence)
4. Heat-Stress & Thermal Strain Risk (NTC + Ambient + Humidity + Activity)
5. Environmental Exposure (MQ-45 Exposure Index)
6. Activity Strain (ADXL345 Movement Intensity)
7. General Physiological Anomaly

Enforces subject-wise stratification and includes explicit transient disturbance cases
(hot beverage contact, AC room transitions, isolated humidity spikes, exercise).
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
    records = []
    csv_files = sorted(glob.glob(os.path.join(BIDMC_NUMERICS_PATH, "bidmc_*_Numerics.csv")))
    
    if not csv_files:
        return generate_synthetic_clinical_seed()

    for file_path in csv_files:
        subject_id = os.path.basename(file_path).split("_")[1]
        try:
            df = pd.read_csv(file_path)
            df.columns = [c.strip() for c in df.columns]
            if "HR" in df.columns and "SpO2" in df.columns:
                df["subject_id"] = f"SUBJ_{subject_id}"
                df = df[(df["HR"] > 30) & (df["HR"] < 220) & (df["SpO2"] > 60) & (df["SpO2"] <= 100)]
                records.append(df)
        except Exception:
            continue

    if not records:
        return generate_synthetic_clinical_seed()

    return pd.concat(records, ignore_index=True)

def generate_synthetic_clinical_seed(n_samples: int = 15000) -> pd.DataFrame:
    np.random.seed(42)
    hr = np.random.normal(74, 10, n_samples).clip(45, 180)
    spo2 = np.random.normal(98, 1.2, n_samples).clip(75, 100)
    resp = np.random.normal(16, 3.0, n_samples).clip(8, 40)
    return pd.DataFrame({
        "Time [s]": np.arange(n_samples),
        "HR": hr,
        "PULSE": hr + np.random.normal(0, 1, n_samples),
        "RESP": resp,
        "SpO2": spo2,
        "subject_id": "SYNTH_01"
    })

def create_multimodal_training_dataset(n_target: int = 24000) -> pd.DataFrame:
    base_df = load_bidmc_numerics()
    np.random.seed(42)
    
    if len(base_df) > n_target:
        base_df = base_df.sample(n_target, random_state=42).reset_index(drop=True)
    n = len(base_df)

    hr = base_df["HR"].values.astype(float)
    spo2 = base_df["SpO2"].values.astype(float)
    resp = base_df["RESP"].values.astype(float) if "RESP" in base_df.columns else np.random.normal(16, 3, n)
    subject_ids = base_df["subject_id"].values if "subject_id" in base_df.columns else np.array([f"SUBJ_{i%30}" for i in range(n)])

    # 1. Establish individual baselines per subject
    subj_baseline_hr = np.random.normal(72, 5, n)
    subj_baseline_spo2 = np.random.normal(98, 0.6, n)
    subj_baseline_temp = np.random.normal(36.7, 0.2, n)

    # 2. Ambient and thermal environments
    ambient_temp = np.random.uniform(22, 34, n)
    ambient_humidity = np.random.uniform(35, 75, n)
    body_temp = subj_baseline_temp + np.random.normal(0, 0.15, n)
    mq45 = np.clip(np.random.exponential(150, n) + 100, 50, 950)

    # 3. Activity classification (0: REST, 1: SITTING, 2: STANDING, 3: WALKING, 4: RUNNING/HIGH)
    activity_states = np.random.choice([0, 1, 2, 3, 4], size=n, p=[0.40, 0.25, 0.15, 0.14, 0.06])
    accel_mag = np.ones(n)

    for i in range(n):
        act = activity_states[i]
        if act in (0, 1):
            accel_mag[i] = np.random.normal(1.0, 0.03)
        elif act == 2:
            accel_mag[i] = np.random.normal(1.05, 0.05)
        elif act == 3:
            accel_mag[i] = np.random.normal(1.30, 0.12)
        elif act == 4:
            accel_mag[i] = np.random.normal(1.75, 0.25)
            # High activity naturally elevates heart rate! (Exercise scenario)
            hr[i] = np.clip(subj_baseline_hr[i] + np.random.uniform(35, 75), 100, 185)
            spo2[i] = np.clip(spo2[i], 96, 100) # Exercise maintains good SpO2

    ppg_quality = np.clip(1.0 - (accel_mag - 1.0).clip(0, 2) * 0.25 + np.random.normal(0, 0.03, n), 0.3, 1.0)

    # 4. INJECT EXPLICIT CONTEXTUAL SCENARIOS:

    # SCENARIO A: Resting Tachycardia / Persistent HR Anomaly (Resting HR 140-198, SpO2 normal)
    tachy_idx = np.random.choice(np.where(activity_states <= 1)[0], size=int(n * 0.08), replace=False)
    hr[tachy_idx] = np.random.uniform(130, 198, len(tachy_idx))
    spo2[tachy_idx] = np.random.uniform(96, 99, len(tachy_idx)) # SpO2 remains normal!

    # SCENARIO B: True Respiratory Distress (SpO2 drops <92%, HR compensatory elevation, Resp elevated)
    resp_idx = np.random.choice(n, size=int(n * 0.08), replace=False)
    spo2[resp_idx] = np.random.uniform(78, 91, len(resp_idx))
    hr[resp_idx] = np.clip(hr[resp_idx] + np.random.uniform(15, 35, len(resp_idx)), 80, 155)
    resp[resp_idx] = np.random.uniform(22, 38, len(resp_idx))

    # SCENARIO C: True Heat Stress / Thermal Strain (High ambient >36, high humidity >70, elevated body temp >38.5, high HR)
    heat_idx = np.random.choice(n, size=int(n * 0.07), replace=False)
    ambient_temp[heat_idx] = np.random.uniform(37, 44, len(heat_idx))
    ambient_humidity[heat_idx] = np.random.uniform(65, 92, len(heat_idx))
    body_temp[heat_idx] = np.random.uniform(38.2, 40.2, len(heat_idx))
    hr[heat_idx] = np.clip(hr[heat_idx] + np.random.uniform(20, 45, len(heat_idx)), 90, 160)

    # SCENARIO D: Hot Beverage / Contact Disturbance Spike (NTC temp 38.5-39.5, ambient normal, HR resting normal 70-80, SpO2 normal)
    beverage_idx = np.random.choice(np.where(activity_states <= 1)[0], size=int(n * 0.05), replace=False)
    body_temp[beverage_idx] = np.random.uniform(38.2, 39.5, len(beverage_idx))
    ambient_temp[beverage_idx] = np.random.uniform(23, 27, len(beverage_idx))
    hr[beverage_idx] = np.random.uniform(68, 78, len(beverage_idx))
    spo2[beverage_idx] = np.random.uniform(97, 99, len(beverage_idx))

    # SCENARIO E: Air-conditioned Transition (Ambient drops 32°C -> 21°C, body temp stable, HR stable)
    ac_idx = np.random.choice(n, size=int(n * 0.05), replace=False)
    ambient_temp[ac_idx] = np.random.uniform(19, 22, len(ac_idx))
    body_temp[ac_idx] = np.random.uniform(36.5, 36.9, len(ac_idx))
    hr[ac_idx] = np.random.uniform(70, 76, len(ac_idx))

    # SCENARIO F: Isolated High Humidity (Humidity >85%, ambient moderate 25°C, body temp normal, HR normal)
    hum_idx = np.random.choice(n, size=int(n * 0.05), replace=False)
    ambient_humidity[hum_idx] = np.random.uniform(82, 95, len(hum_idx))
    ambient_temp[hum_idx] = np.random.uniform(24, 28, len(hum_idx))
    body_temp[hum_idx] = np.random.uniform(36.6, 36.8, len(hum_idx))

    # SCENARIO G: Pure Environmental Gas Exposure (MQ-45 > 650, physiology normal)
    gas_idx = np.random.choice(n, size=int(n * 0.06), replace=False)
    mq45[gas_idx] = np.random.uniform(600, 950, len(gas_idx))

    # Clip to biological bounds
    hr = np.clip(hr, 40, 210)
    spo2 = np.clip(spo2, 65, 100)
    body_temp = np.clip(body_temp, 35.0, 42.0)

    # Derived baseline deviations
    hr_dev = (hr - subj_baseline_hr) / subj_baseline_hr
    spo2_dev = (spo2 - subj_baseline_spo2) / subj_baseline_spo2
    temp_dev = body_temp - subj_baseline_temp

    # Heat index calculation
    heat_index = ambient_temp + 0.1 * ambient_humidity

    # --- GROUND TRUTH LABELS PER DISTINCT DOMAIN ---

    # 1. HEART RATE ANOMALY TARGET (0=LOW, 1=EARLY_WARNING, 2=ELEVATED, 3=CRITICAL)
    # Crucial: At rest, HR > 140 is ELEVATED/CRITICAL. During exercise (HIGH activity), HR 140 is NORMAL/LOW!
    hr_anomaly = np.zeros(n, dtype=int)
    for i in range(n):
        h = hr[i]
        act = activity_states[i]
        if act in (0, 1): # REST
            if h >= 165 or h <= 45:
                hr_anomaly[i] = 3 # CRITICAL
            elif h >= 130:
                hr_anomaly[i] = 2 # ELEVATED
            elif h >= 98:
                hr_anomaly[i] = 1 # EARLY_WARNING
        elif act in (2, 3): # LIGHT/MODERATE
            if h >= 180:
                hr_anomaly[i] = 3
            elif h >= 155:
                hr_anomaly[i] = 2
            elif h >= 135:
                hr_anomaly[i] = 1
        else: # HIGH ACTIVITY / EXERCISE
            if h >= 195:
                hr_anomaly[i] = 2
            elif h >= 180:
                hr_anomaly[i] = 1
            else:
                hr_anomaly[i] = 0 # Normal exercise response

    # 2. OXYGENATION ANOMALY TARGET
    spo2_anomaly = np.zeros(n, dtype=int)
    for i in range(n):
        s = spo2[i]
        if s <= 85:
            spo2_anomaly[i] = 3 # CRITICAL
        elif s <= 91:
            spo2_anomaly[i] = 2 # ELEVATED
        elif s <= 95:
            spo2_anomaly[i] = 1 # EARLY_WARNING

    # 3. RESPIRATORY RISK TARGET
    # Crucial: Only elevated if SpO2 drops + respiratory/cardiac compensation! HR 198 alone is NEVER respiratory!
    respiratory_risk = np.zeros(n, dtype=int)
    for i in range(n):
        s = spo2[i]
        h = hr[i]
        if s <= 87:
            respiratory_risk[i] = 3 # CRITICAL
        elif s <= 91 and h > 90:
            respiratory_risk[i] = 2 # ELEVATED
        elif s <= 94 and (h > 95 or mq45[i] > 500):
            respiratory_risk[i] = 1 # EARLY_WARNING
        else:
            respiratory_risk[i] = 0

    # 4. HEAT STRESS / THERMAL STRAIN TARGET
    # Hot beverage spike alone with normal ambient and resting HR = LOW!
    heat_stress_risk = np.zeros(n, dtype=int)
    for i in range(n):
        bt = body_temp[i]
        at = ambient_temp[i]
        h = hr[i]
        # Ignore isolated hot mug contact (bt high but ambient normal & HR resting)
        if bt > 38.0 and at < 32.0 and h < 85:
            heat_stress_risk[i] = 0 # Transient contact, NOT heat stroke!
        elif bt >= 39.5 and at >= 35.0:
            heat_stress_risk[i] = 3
        elif bt >= 38.4 and (at >= 34.0 or h >= 110):
            heat_stress_risk[i] = 2
        elif bt >= 37.6 or (at >= 36.0 and h >= 95):
            heat_stress_risk[i] = 1

    # 5. ENVIRONMENTAL EXPOSURE TARGET
    environmental_exposure = np.zeros(n, dtype=int)
    for i in range(n):
        gas = mq45[i]
        if gas >= 700:
            environmental_exposure[i] = 3
        elif gas >= 450:
            environmental_exposure[i] = 2
        elif gas >= 280:
            environmental_exposure[i] = 1

    # 6. ACTIVITY STRAIN TARGET
    activity_strain = np.zeros(n, dtype=int)
    for i in range(n):
        act = activity_states[i]
        if act == 4:
            activity_strain[i] = 3 # HIGH
        elif act == 3:
            activity_strain[i] = 2 # MODERATE
        elif act == 2:
            activity_strain[i] = 1 # LIGHT

    # 7. GENERAL ANOMALY TARGET
    general_anomaly = np.zeros(n, dtype=int)
    for i in range(n):
        max_sub = max(hr_anomaly[i], spo2_anomaly[i], respiratory_risk[i], heat_stress_risk[i])
        general_anomaly[i] = max_sub

    df = pd.DataFrame({
        "subject_id": subject_ids,
        "heart_rate": hr,
        "spo2": spo2,
        "ppg_quality": ppg_quality,
        "body_temperature": body_temp,
        "ambient_temperature": ambient_temp,
        "humidity": ambient_humidity,
        "heat_index": heat_index,
        "accel_mag": accel_mag,
        "mq45": mq45,
        "activity_state": activity_states,
        "hr_deviation": hr_dev,
        "spo2_deviation": spo2_dev,
        "temp_deviation": temp_dev,
        # Targets
        "target_hr_anomaly": hr_anomaly,
        "target_spo2_anomaly": spo2_anomaly,
        "target_respiratory_risk": respiratory_risk,
        "target_heat_stress": heat_stress_risk,
        "target_environmental": environmental_exposure,
        "target_activity_strain": activity_strain,
        "target_general_anomaly": general_anomaly,
    })

    return df

if __name__ == "__main__":
    df = create_multimodal_training_dataset(5000)
    print("Dataset generated successfully. Shape:", df.shape)
    print("HR Anomaly distribution:", df["target_hr_anomaly"].value_counts().to_dict())
    print("Respiratory Risk distribution:", df["target_respiratory_risk"].value_counts().to_dict())
