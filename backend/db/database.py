"""
AAROGYA-SHIELD: MongoDB Storage & Traceability Engine
Manages document persistence across:
sensor_readings, feature_vectors, predictions, risk_events, alerts, baselines, devices.
Ensures every prediction and alert is traceable back to raw sensor telemetry.
"""

import os
import datetime
import pymongo
from typing import Dict, Any, List, Optional

MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
DB_NAME = os.getenv("DB_NAME", "aarogya_shield")

class Database:
    def __init__(self):
        self.client = None
        self.db = None
        self.is_mock = False
        self._connect()

    def _connect(self):
        try:
            self.client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
            # Trigger server selection
            self.client.server_info()
            self.db = self.client[DB_NAME]
            print(f"[Database] Successfully connected to live MongoDB at {MONGO_URI} (Database: {DB_NAME}).")
            self._ensure_indexes()
        except Exception as e:
            print(f"[Database] Live MongoDB connection failed ({e}). Falling back to in-memory Mongomock.")
            import mongomock
            self.client = mongomock.MongoClient()
            self.db = self.client[DB_NAME]
            self.is_mock = True
            self._ensure_indexes()

    def _ensure_indexes(self):
        try:
            self.db.sensor_readings.create_index([("device_id", 1), ("timestamp", -1)])
            self.db.predictions.create_index([("reading_id", 1)])
            self.db.alerts.create_index([("alert_id", 1)], unique=True)
            self.db.alerts.create_index([("timestamp", -1)])
            self.db.baselines.create_index([("device_id", 1)], unique=True)
        except Exception as e:
            pass

    def insert_sensor_reading(self, reading: Dict[str, Any]) -> str:
        doc = dict(reading)
        if "timestamp" not in doc or not doc["timestamp"]:
            doc["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
        res = self.db.sensor_readings.insert_one(doc)
        return str(res.inserted_id)

    def insert_feature_vector(self, reading_id: str, features: Dict[str, Any]):
        doc = dict(features)
        doc["reading_id"] = reading_id
        if "timestamp" not in doc or not doc["timestamp"]:
            doc["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
        self.db.feature_vectors.insert_one(doc)

    def insert_prediction(self, reading_id: str, prediction: Dict[str, Any]):
        doc = dict(prediction)
        doc["reading_id"] = reading_id
        if "timestamp" not in doc or not doc["timestamp"]:
            doc["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
        self.db.predictions.insert_one(doc)

    def insert_risk_event(self, reading_id: str, risk_event: Dict[str, Any]):
        doc = dict(risk_event)
        doc["reading_id"] = reading_id
        if "timestamp" not in doc or not doc["timestamp"]:
            doc["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
        self.db.risk_events.insert_one(doc)

    def save_alert(self, alert: Dict[str, Any]):
        doc = dict(alert)
        self.db.alerts.update_one(
            {"alert_id": doc["alert_id"]},
            {"$set": doc},
            upsert=True
        )

    def get_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        cursor = self.db.alerts.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
        return list(cursor)

    def get_latest_alert(self) -> Optional[Dict[str, Any]]:
        doc = self.db.alerts.find_one({}, {"_id": 0}, sort=[("timestamp", -1)])
        return doc

    def acknowledge_alert(self, alert_id: str) -> Optional[Dict[str, Any]]:
        ack_time = datetime.datetime.utcnow().isoformat() + "Z"
        self.db.alerts.update_one(
            {"alert_id": alert_id},
            {"$set": {"acknowledged": True, "acknowledged_at": ack_time}}
        )
        return self.db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})

    def save_baseline(self, baseline_dict: Dict[str, Any]):
        self.db.baselines.update_one(
            {"device_id": baseline_dict["device_id"]},
            {"$set": baseline_dict},
            upsert=True
        )

    def get_baseline(self, device_id: str) -> Optional[Dict[str, Any]]:
        return self.db.baselines.find_one({"device_id": device_id}, {"_id": 0})

    def register_device(self, device_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        doc = {
            "device_id": device_id,
            "registered_at": datetime.datetime.utcnow().isoformat() + "Z",
            "metadata": metadata,
            "status": "ONLINE",
        }
        self.db.devices.update_one({"device_id": device_id}, {"$set": doc}, upsert=True)
        return doc

    def get_latest_reading(self, device_id: str = "ESP32-001") -> Optional[Dict[str, Any]]:
        doc = self.db.sensor_readings.find_one({"device_id": device_id}, sort=[("timestamp", -1)])
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    def get_latest_prediction(self, device_id: str = "ESP32-001") -> Optional[Dict[str, Any]]:
        doc = self.db.predictions.find_one({}, sort=[("timestamp", -1)])
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    def get_risk_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        cursor = self.db.risk_events.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
        return list(cursor)

_db_instance: Optional[Database] = None

def get_db() -> Database:
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
