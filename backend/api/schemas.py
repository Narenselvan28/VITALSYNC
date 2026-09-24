"""
VITALSYNC: Pydantic Schemas
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
    body_temperature: float = Field(default=36.7, ge=20.0, le=45.0, description="10K NTC contact/skin temperature in °C")
    ambient_temperature: float = Field(default=28.0, ge=-25.0, le=65.0, description="Ambient temperature in °C")
    humidity: float = Field(default=60.0, ge=0.0, le=100.0, description="Ambient relative humidity in %")
    accel_x: Optional[float] = Field(default=0.02, description="ADXL345 acceleration X axis in g")
    accel_y: Optional[float] = Field(default=0.01, description="ADXL345 acceleration Y axis in g")
    accel_z: Optional[float] = Field(default=0.98, description="ADXL345 acceleration Z axis in g")
    mq45: float = Field(default=180.0, ge=0, le=2000, description="MQ-45 environmental exposure indicator (0-1000 index)")
    latitude: Optional[float] = Field(default=10.662, description="GPS NEO-7 latitude")
    longitude: Optional[float] = Field(default=76.891, description="GPS NEO-7 longitude")
    gps_fix: Optional[bool] = Field(default=True, description="GPS fix status")
    ntc_adc: Optional[float] = Field(default=None, description="Raw 12-bit ADC reading for NTC thermistor")
    adxl_available: Optional[bool] = Field(default=True, description="Whether accelerometer is connected and healthy")
    weather_status: Optional[str] = Field(default="ONLINE", description="Weather service connectivity")
    sim800l_status: Optional[str] = Field(default="READY", description="Cellular modem status")
    is_simulator: Optional[bool] = Field(default=False, description="Whether reading originated from simulator")

class DeviceRegisterSchema(BaseModel):
    device_id: str = "ESP32-001"
    device_type: str = "ESP32-MAX30102-ADXL345-NTC-MQ45"
    firmware_version: str = "v2.0.0"
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

class HealthProfileSchema(BaseModel):
    device_id: Optional[str] = "ESP32-001"
    age: int = Field(default=32, ge=1, le=120, description="Age in years")
    sex: str = Field(default="M", description="Sex: M, F, Other, Prefer not to say")
    height_cm: Optional[float] = Field(default=170.0, ge=50, le=250, description="Height in cm")
    weight_kg: Optional[float] = Field(default=70.0, ge=20, le=300, description="Weight in kg")
    conditions: List[str] = Field(default=["none"], description="List of health conditions")
    medications: Optional[List[str]] = Field(default=[], description="Current medications list")
    medication_context: Optional[str] = Field(default=None, description="Free text or structured medication context")

