"""
AAROGYA-SHIELD: Patient Profile & Context Management Engine
Manages personalized user health profiles, chronic condition contexts,
medication contexts, profile versioning, and privacy guards.
Ensures non-diagnostic medical framing: wearable sensors monitor physiological
strain and early-warning deviations without diagnosing diseases.
"""

import json
import datetime
from typing import Dict, Any, List, Optional
from backend.db.database import get_db

AVAILABLE_CONDITIONS = [
    {"id": "none", "label": "No known condition", "category": "general"},
    {"id": "asthma", "label": "Asthma / respiratory condition", "category": "respiratory"},
    {"id": "cardiovascular", "label": "Heart / cardiovascular condition", "category": "cardiac"},
    {"id": "diabetes", "label": "Diabetes", "category": "metabolic"},
    {"id": "hypertension", "label": "Hypertension", "category": "cardiac"},
    {"id": "copd", "label": "COPD", "category": "respiratory"},
    {"id": "kidney", "label": "Kidney condition", "category": "renal"},
    {"id": "other_respiratory", "label": "Other respiratory condition", "category": "respiratory"},
    {"id": "other_cardiovascular", "label": "Other cardiovascular condition", "category": "cardiac"},
    {"id": "other", "label": "Other", "category": "other"},
    {"id": "prefer_not_to_say", "label": "Prefer not to say", "category": "privacy"},
]

DEFAULT_PROFILE: Dict[str, Any] = {
    "device_id": "ESP32-001",
    "age": 32,
    "sex": "M",
    "height_cm": 175.0,
    "weight_kg": 70.0,
    "conditions": ["none"],
    "medications": [],
    "medication_context": "UNKNOWN",
    "profile_version": "1.0",
    "created_at": datetime.datetime.utcnow().isoformat() + "Z",
    "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
    "baseline_status": "LEARNING", # "LEARNING" | "CALIBRATED"
}

class PatientProfileManager:
    """
    Manages local storage, versioning, and contextual transformation
    of the user's personal health profile.
    """
    def __init__(self, device_id: str = "ESP32-001"):
        self.device_id = device_id
        self._active_profile: Dict[str, Any] = dict(DEFAULT_PROFILE)
        self._profile_history: List[Dict[str, Any]] = []
        self._profile_changed: bool = False
        self._load_from_db()

    def _load_from_db(self):
        try:
            db = get_db()
            doc = db.db.patient_profiles.find_one({"device_id": self.device_id}, {"_id": 0})
            if doc:
                self._active_profile = doc
            else:
                self._save_to_db()
        except Exception:
            pass

    def _save_to_db(self):
        try:
            db = get_db()
            db.db.patient_profiles.update_one(
                {"device_id": self.device_id},
                {"$set": self._active_profile},
                upsert=True
            )
        except Exception:
            pass

    def get_profile(self) -> Dict[str, Any]:
        """Returns the active sanitized patient profile."""
        return dict(self._active_profile)

    def set_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates the health profile with version incrementing.
        Section 13: Profile change does NOT destroy learned baseline.
        """
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"

        # Archive old profile
        old_profile = dict(self._active_profile)
        self._profile_history.append(old_profile)

        # Parse version
        try:
            old_ver = float(self._active_profile.get("profile_version", "1.0"))
            new_ver = f"{round(old_ver + 0.1, 1):.1f}"
        except Exception:
            new_ver = "1.1"

        # Sanitize conditions list (ensure list of strings)
        raw_conditions = profile_data.get("conditions", [])
        if isinstance(raw_conditions, str):
            raw_conditions = [raw_conditions]
        
        # If 'none' or 'prefer_not_to_say' is mixed with others, prioritize specific conditions
        if len(raw_conditions) > 1 and "none" in raw_conditions:
            raw_conditions.remove("none")

        # Sanitize medication context (Section 2)
        meds = profile_data.get("medications", [])
        med_ctx = profile_data.get("medication_context")
        if not med_ctx:
            if meds:
                med_ctx = ", ".join([str(m) for m in meds])
            else:
                med_ctx = "UNKNOWN"

        updated = {
            "device_id": self.device_id,
            "age": int(profile_data.get("age", self._active_profile.get("age", 30))),
            "sex": str(profile_data.get("sex", self._active_profile.get("sex", "Prefer not to say"))),
            "height_cm": float(profile_data.get("height_cm", self._active_profile.get("height_cm", 170.0))),
            "weight_kg": float(profile_data.get("weight_kg", self._active_profile.get("weight_kg", 70.0))),
            "conditions": raw_conditions,
            "medications": meds,
            "medication_context": med_ctx,
            "profile_version": new_ver,
            "created_at": self._active_profile.get("created_at", now_iso),
            "updated_at": now_iso,
            "baseline_status": self._active_profile.get("baseline_status", "LEARNING"),
        }

        self._active_profile = updated
        self._profile_changed = True
        self._save_to_db()

        return dict(self._active_profile)

    def set_baseline_status(self, status: str):
        """Updates baseline status ('LEARNING' or 'CALIBRATED')."""
        self._active_profile["baseline_status"] = status
        self._save_to_db()

    def get_active_condition_contexts(self) -> List[str]:
        """
        Derives active physiological monitoring contexts from configured conditions.
        Section 11: Combines multiple conditions without crude threshold addition.
        """
        conditions = self._active_profile.get("conditions", [])
        contexts = []

        if any(c in conditions for c in ["asthma", "copd", "other_respiratory"]):
            contexts.append("respiratory_monitoring")
        if any(c in conditions for c in ["cardiovascular", "hypertension", "other_cardiovascular"]):
            contexts.append("cardiovascular_monitoring")
        if "diabetes" in conditions:
            contexts.append("metabolic_context")
        if "kidney" in conditions:
            contexts.append("renal_fluid_context")
        if not contexts or "none" in conditions:
            contexts.append("general_monitoring")

        return contexts

    def get_privacy_sanitized_location_request(self, lat: float, lon: float) -> Dict[str, float]:
        """
        Section 16: Privacy guard.
        Ensures NO profile or health condition data is ever sent to external APIs.
        Only minimal coordinates are passed for contextual weather lookup.
        """
        return {"latitude": round(lat, 3), "longitude": round(lon, 3)}

_profile_manager_instances: Dict[str, PatientProfileManager] = {}

def get_patient_profile_manager(device_id: str = "ESP32-001") -> PatientProfileManager:
    global _profile_manager_instances
    if device_id not in _profile_manager_instances:
        _profile_manager_instances[device_id] = PatientProfileManager(device_id)
    return _profile_manager_instances[device_id]
