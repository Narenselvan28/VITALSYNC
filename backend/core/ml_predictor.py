"""
VITALSYNC: ML Predictor Wrapper
Provides a lightweight interface to the trained XGBoost and Tiny TCN models.
Runs in < 5 ms on edge Raspberry Pi 4 hardware.
"""

from typing import Dict, Any
from backend.ml.model_registry import get_model_registry, ModelRegistry

class MLPredictor:
    def __init__(self):
        self.registry = get_model_registry()

    def predict(self, feature_vector: Dict[str, Any]) -> Dict[str, Any]:
        return self.registry.predict_all(feature_vector)

_predictor = MLPredictor()

def get_ml_predictor() -> MLPredictor:
    return _predictor
