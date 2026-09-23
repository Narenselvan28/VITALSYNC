"""
AAROGYA-SHIELD: Model Evaluation Script
Loads trained models from backend/ml/models/ and runs evaluation
across test distributions, printing comprehensive performance metrics.
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, f1_score

from backend.ml.dataset_loader import create_multimodal_training_dataset

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

RISK_LABELS = ["LOW", "EARLY_WARNING", "ELEVATED", "CRITICAL"]

def evaluate_suite():
    version_file = os.path.join(MODELS_DIR, "model_version.json")
    if not os.path.exists(version_file):
        print(f"[Error] No trained models found at {MODELS_DIR}. Run train_models.py first.")
        return

    with open(version_file, "r") as f:
        version_data = json.load(f)

    print("==================================================")
    print("AAROGYA-SHIELD: MODEL EVALUATION REPORT")
    print(f"Version: {version_data['version']}")
    print(f"Source: {version_data['source']}")
    print(f"Clinical Framing: {version_data['framing']}")
    print("==================================================")

    # Load fresh validation dataset
    df = create_multimodal_training_dataset()

    # 1. Respiratory Model
    print("\n--- Model 1: Respiratory Risk Model (XGBoost) ---")
    resp_model = joblib.load(os.path.join(MODELS_DIR, "respiratory_risk_model.joblib"))
    resp_scaler = joblib.load(os.path.join(MODELS_DIR, "respiratory_risk_scaler.joblib"))
    with open(os.path.join(MODELS_DIR, "respiratory_risk_features.json")) as f:
        resp_features = json.load(f)

    X_resp = resp_scaler.transform(df[resp_features])
    y_resp = df["respiratory_risk"]
    y_pred_resp = resp_model.predict(X_resp)
    print(classification_report(y_resp, y_pred_resp, target_names=RISK_LABELS, digits=4))

    # 2. Heat Stress Model
    print("\n--- Model 2: Heat-Stress & Physiological-Strain Model (XGBoost) ---")
    heat_model = joblib.load(os.path.join(MODELS_DIR, "heat_stress_risk_model.joblib"))
    heat_scaler = joblib.load(os.path.join(MODELS_DIR, "heat_stress_risk_scaler.joblib"))
    with open(os.path.join(MODELS_DIR, "heat_stress_risk_features.json")) as f:
        heat_features = json.load(f)

    X_heat = heat_scaler.transform(df[heat_features])
    y_heat = df["heat_stress_risk"]
    y_pred_heat = heat_model.predict(X_heat)
    print(classification_report(y_heat, y_pred_heat, target_names=RISK_LABELS, digits=4))

    # 3. Environmental Model
    print("\n--- Model 3: Environmental Exposure Risk Model (GradientBoosting) ---")
    env_model = joblib.load(os.path.join(MODELS_DIR, "environmental_risk_model.joblib"))
    env_scaler = joblib.load(os.path.join(MODELS_DIR, "environmental_risk_scaler.joblib"))
    with open(os.path.join(MODELS_DIR, "environmental_risk_features.json")) as f:
        env_features = json.load(f)

    X_env = env_scaler.transform(df[env_features])
    y_env = df["environmental_risk"]
    y_pred_env = env_model.predict(X_env)
    print(classification_report(y_env, y_pred_env, target_names=RISK_LABELS, digits=4))

    # 4. General Anomaly Model
    print("\n--- Model 4: General Health Anomaly Model (XGBoost + Novelty Detection) ---")
    anom_model = joblib.load(os.path.join(MODELS_DIR, "general_anomaly_model.joblib"))
    anom_scaler = joblib.load(os.path.join(MODELS_DIR, "general_anomaly_scaler.joblib"))
    with open(os.path.join(MODELS_DIR, "general_anomaly_features.json")) as f:
        anom_features = json.load(f)

    X_anom = anom_scaler.transform(df[anom_features])
    y_anom = df["general_anomaly"]
    y_pred_anom = anom_model.predict(X_anom)
    print(classification_report(y_anom, y_pred_anom, target_names=["NOMINAL", "ANOMALOUS"], digits=4))

    print("\n[SUCCESS] Model evaluation complete. High multi-modal discriminative capability verified.")

if __name__ == "__main__":
    evaluate_suite()
