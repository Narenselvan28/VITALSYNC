"""
AAROGYA-SHIELD: Model Training Pipeline
Trains four Edge-AI risk and anomaly models:
1. General Health Anomaly Model (IsolationForest / GradientBoosting)
2. Respiratory Risk Model (XGBoost / GradientBoosting Classifier)
3. Heat-Stress & Physiological-Strain Risk Model (XGBoost / GradientBoosting Classifier)
4. Environmental Exposure Risk Model (XGBoost / GradientBoosting Classifier)

Saves models, scalers, feature column lists, training metrics, and model versions to backend/ml/models/
"""

import os
import json
import joblib
import datetime
import numpy as np
import pandas as pd
from typing import Dict, Any, List

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, f1_score, accuracy_score, precision_score, recall_score, confusion_matrix
from sklearn.ensemble import GradientBoostingClassifier, IsolationForest
import xgboost as xgb

from backend.ml.dataset_loader import create_multimodal_training_dataset

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.makedirs(MODELS_DIR, exist_ok=True)

VERSION = "1.0.0-edge"

# Feature definitions for each model
RESPIRATORY_FEATURES = [
    "heart_rate",
    "spo2",
    "ppg_quality",
    "hr_deviation",
    "spo2_deviation",
    "mq45",
    "activity_state",
]

HEAT_STRESS_FEATURES = [
    "body_temperature",
    "ambient_temperature",
    "humidity",
    "heat_index",
    "heart_rate",
    "temp_deviation",
    "hr_deviation",
    "activity_state",
]

ENVIRONMENTAL_FEATURES = [
    "mq45",
    "ambient_temperature",
    "humidity",
    "heat_index",
]

GENERAL_ANOMALY_FEATURES = [
    "heart_rate",
    "spo2",
    "ppg_quality",
    "body_temperature",
    "ambient_temperature",
    "humidity",
    "accel_mag",
    "mq45",
    "activity_state",
    "hr_deviation",
    "spo2_deviation",
    "temp_deviation",
]


def train_respiratory_model(df: pd.DataFrame) -> Dict[str, Any]:
    print("\n--- Training Respiratory Risk Model (XGBoost) ---")
    X = df[RESPIRATORY_FEATURES]
    y = df["respiratory_risk"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Use XGBoost Classifier with edge-friendly shallow trees
    model = xgb.XGBClassifier(
        n_estimators=120,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        eval_metric="mlogloss",
    )
    model.fit(X_train_scaled, y_train)

    y_pred = model.predict(X_test_scaled)
    y_prob = model.predict_proba(X_test_scaled)

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1_macro": float(f1_score(y_test, y_pred, average="macro")),
        "precision_macro": float(precision_score(y_test, y_pred, average="macro")),
        "recall_macro": float(recall_score(y_test, y_pred, average="macro")),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
    }
    print(f"Respiratory Risk Accuracy: {metrics['accuracy']:.4f}, F1-Macro: {metrics['f1_macro']:.4f}")

    # Save artifacts
    prefix = "respiratory_risk"
    joblib.dump(model, os.path.join(MODELS_DIR, f"{prefix}_model.joblib"))
    joblib.dump(scaler, os.path.join(MODELS_DIR, f"{prefix}_scaler.joblib"))
    
    with open(os.path.join(MODELS_DIR, f"{prefix}_features.json"), "w") as f:
        json.dump(RESPIRATORY_FEATURES, f, indent=2)
        
    with open(os.path.join(MODELS_DIR, f"{prefix}_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    return metrics


def train_heat_stress_model(df: pd.DataFrame) -> Dict[str, Any]:
    print("\n--- Training Heat-Stress Risk Model (XGBoost) ---")
    X = df[HEAT_STRESS_FEATURES]
    y = df["heat_stress_risk"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        eval_metric="mlogloss",
    )
    model.fit(X_train_scaled, y_train)

    y_pred = model.predict(X_test_scaled)

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1_macro": float(f1_score(y_test, y_pred, average="macro")),
        "precision_macro": float(precision_score(y_test, y_pred, average="macro")),
        "recall_macro": float(recall_score(y_test, y_pred, average="macro")),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
    }
    print(f"Heat-Stress Risk Accuracy: {metrics['accuracy']:.4f}, F1-Macro: {metrics['f1_macro']:.4f}")

    prefix = "heat_stress_risk"
    joblib.dump(model, os.path.join(MODELS_DIR, f"{prefix}_model.joblib"))
    joblib.dump(scaler, os.path.join(MODELS_DIR, f"{prefix}_scaler.joblib"))
    
    with open(os.path.join(MODELS_DIR, f"{prefix}_features.json"), "w") as f:
        json.dump(HEAT_STRESS_FEATURES, f, indent=2)
        
    with open(os.path.join(MODELS_DIR, f"{prefix}_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    return metrics


def train_environmental_model(df: pd.DataFrame) -> Dict[str, Any]:
    print("\n--- Training Environmental Exposure Risk Model (GradientBoosting) ---")
    X = df[ENVIRONMENTAL_FEATURES]
    y = df["environmental_risk"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = GradientBoostingClassifier(
        n_estimators=80,
        max_depth=3,
        learning_rate=0.1,
        random_state=42,
    )
    model.fit(X_train_scaled, y_train)

    y_pred = model.predict(X_test_scaled)

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1_macro": float(f1_score(y_test, y_pred, average="macro")),
        "precision_macro": float(precision_score(y_test, y_pred, average="macro")),
        "recall_macro": float(recall_score(y_test, y_pred, average="macro")),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
    }
    print(f"Environmental Risk Accuracy: {metrics['accuracy']:.4f}, F1-Macro: {metrics['f1_macro']:.4f}")

    prefix = "environmental_risk"
    joblib.dump(model, os.path.join(MODELS_DIR, f"{prefix}_model.joblib"))
    joblib.dump(scaler, os.path.join(MODELS_DIR, f"{prefix}_scaler.joblib"))
    
    with open(os.path.join(MODELS_DIR, f"{prefix}_features.json"), "w") as f:
        json.dump(ENVIRONMENTAL_FEATURES, f, indent=2)
        
    with open(os.path.join(MODELS_DIR, f"{prefix}_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    return metrics


def train_general_anomaly_model(df: pd.DataFrame) -> Dict[str, Any]:
    print("\n--- Training General Anomaly Model (Ensemble Anomaly + Classifier) ---")
    X = df[GENERAL_ANOMALY_FEATURES]
    y = df["general_anomaly"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Supervised calibrated anomaly classifier for edge deployment
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.08,
        random_state=42,
        eval_metric="logloss",
    )
    model.fit(X_train_scaled, y_train)

    # Also train an Isolation Forest on the nominal subset for unsupervised novelty score
    nominal_train = X_train_scaled[y_train == 0]
    iso_forest = IsolationForest(n_estimators=80, contamination=0.08, random_state=42)
    iso_forest.fit(nominal_train)

    y_pred = model.predict(X_test_scaled)

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1": float(f1_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred)),
        "recall": float(recall_score(y_test, y_pred)),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
    }
    print(f"General Anomaly Accuracy: {metrics['accuracy']:.4f}, F1: {metrics['f1']:.4f}")

    prefix = "general_anomaly"
    joblib.dump(model, os.path.join(MODELS_DIR, f"{prefix}_model.joblib"))
    joblib.dump(iso_forest, os.path.join(MODELS_DIR, f"{prefix}_isoforest.joblib"))
    joblib.dump(scaler, os.path.join(MODELS_DIR, f"{prefix}_scaler.joblib"))
    
    with open(os.path.join(MODELS_DIR, f"{prefix}_features.json"), "w") as f:
        json.dump(GENERAL_ANOMALY_FEATURES, f, indent=2)
        
    with open(os.path.join(MODELS_DIR, f"{prefix}_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    return metrics


def train_all_models():
    print(f"Starting AAROGYA-SHIELD Model Training Suite (Version: {VERSION})")
    df = create_multimodal_training_dataset()

    respiratory_metrics = train_respiratory_model(df)
    heat_stress_metrics = train_heat_stress_model(df)
    environmental_metrics = train_environmental_model(df)
    general_anomaly_metrics = train_general_anomaly_model(df)

    version_info = {
        "version": VERSION,
        "trained_at": datetime.datetime.utcnow().isoformat() + "Z",
        "dataset_samples": len(df),
        "source": "PhysioNet BIDMC PPG & Respiration Dataset (v1.0.0) + Multi-Modal Edge Biosignals",
        "models": {
            "respiratory_risk": respiratory_metrics,
            "heat_stress_risk": heat_stress_metrics,
            "environmental_risk": environmental_metrics,
            "general_anomaly": general_anomaly_metrics,
        },
        "framing": "Non-diagnostic early-warning and physiological anomaly screening."
    }

    with open(os.path.join(MODELS_DIR, "model_version.json"), "w") as f:
        json.dump(version_info, f, indent=2)

    print("\n[SUCCESS] All 4 models trained, evaluated, and serialized to backend/ml/models/.")
    return version_info


if __name__ == "__main__":
    train_all_models()
