"""
AAROGYA-SHIELD: Pydantic Schemas
Defines request and response schemas for all REST and WebSocket payloads.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class SensorReadingSchema(BaseModel):
    device_id: str = Field(default="ESP32-001", description="Device identifier")
    timestamp: Optional[str] = Field(default=None, description="ISO8601 UTC timestamp")
    heart_rate: float = Field(..., ge=30, le=240, description="Heart rate in BPM (MAX30102)")
    spo2: float = Field(..., ge=60, le=100, description="Blood oxygen saturation in % (MAX30102)")
    ppg_quality: Optional[float] = Field(default=0.95, ge=0.0, le=1.0, description="PPG signal quality (0-1)")
    body_temperature: float = Field(..., ge=32.0, le=44.0, description="Body temperature in °C")
    ambient_temperature: float = Field(..., ge=-20.0, le=65.0, description="Ambient temperature in °C")
    humidity: float = Field(..., ge=0.0, le=100.0, description="Ambient relative humidity in %")
    accel_x: float = Field(default=0.02, description="ADXL345 acceleration X axis in g")
    accel_y: float = Field(default=0.01, description="ADXL345 acceleration Y axis in g")
    accel_z: float = Field(default=0.98, description="ADXL345 acceleration Z axis in g")
    mq45: float = Field(..., ge=0, le=2000, description="MQ-45 environmental exposure indicator")
    latitude: Optional[float] = Field(default=10.662, description="GPS latitude")
    longitude: Optional[float] = Field(default=76.891, description="GPS longitude")
    is_simulator: Optional[bool] = Field(default=False, description="Whether reading originated from simulator")

class DeviceRegisterSchema(BaseModel):
    device_id: str = "ESP32-001"
    device_type: str = "ESP32-MAX30102-ADXL345"
    firmware_version: str = "v1.0.0"
    patient_name: Optional[str] = "Subject-01"
    patient_age: Optional[int] = 42
    location: Optional[str] = "Ward A / Edge Node"

class BaselineStartSchema(BaseModel):
    device_id: str = "ESP32-001"

class AlertCreateSchema(BaseModel):
    device_id: str = "ESP32-001"
    risk_type: str = "Physiological Anomaly"
    risk_level: str = "EARLY_WARNING"
    message: str = "Manual alert notification"
    contributing_parameters: List[str] = []
    latitude: Optional[float] = 10.662
    longitude: Optional[float] = 76.891

class AlertAckSchema(BaseModel):
    alert_id: str
