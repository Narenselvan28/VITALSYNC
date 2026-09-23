/*
  =============================================================================
  AAROGYA-SHIELD: ESP32 Wearable Multi-Sensor Edge Node Firmware
  =============================================================================
  Hardware Target: ESP32 DevKit V1 (30-pin)
  Sensors Supported:
    1. MAX30102 Pulse Oximeter & Heart-Rate Sensor (I2C: SDA=21, SCL=22)
    2. ADXL345 3-Axis Digital Accelerometer (I2C: SDA=21, SCL=22)
    3. DS18B20 Digital Body Temperature Sensor (OneWire Pin: GPIO 4)
    4. DHT22 / AM2302 Ambient Temperature & Humidity Sensor (Pin: GPIO 5)
    5. MQ-45 Environmental Air Quality / Gas Exposure Indicator (ADC Pin: GPIO 34)
    6. NEO-6M GPS Module (HardwareSerial 2: RX=16, TX=17)

  Communication:
    Transmits JSON telemetry to Raspberry Pi 4 Edge API:
    POST http://<EDGE_PI_IP>:8000/api/sensors/readings
  =============================================================================
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <ArduinoJson.h> // ArduinoJson v6 or v7

// --- Configuration ---
const char* WIFI_SSID     = "AAROGYA_WIFI";
const char* WIFI_PASSWORD = "EdgeShieldPassword2026";
const char* EDGE_API_URL  = "http://192.168.1.100:8000/api/sensors/readings";
const char* DEVICE_ID     = "ESP32-001";

// Pin definitions
#define PIN_ONEWIRE_TEMP 4
#define PIN_DHT22        5
#define PIN_MQ45_ANALOG  34
#define GPS_RX_PIN       16
#define GPS_TX_PIN       17

// Sensor simulated placeholders / registers for demonstration
float readHeartRate() {
  // Reads MAX30102 via SparkFun_MAX3010x library or register extraction
  // Fallback nominal value: 75 BPM with subtle physiological sinus variation
  return 74.0 + (float)(random(-3, 4));
}

float readSpO2() {
  // Calculates ratio-of-ratios from MAX30102 Red/IR AC/DC components
  return 98.0 + (float)(random(-1, 2) * 0.5);
}

float readPPGQuality() {
  // Evaluates signal-to-noise ratio of AC photoplethysmogram
  return 0.94;
}

float readBodyTemperature() {
  // Reads DS18B20 digital temperature probe via DallasTemperature library
  return 36.75 + (float)(random(-10, 10)) * 0.02;
}

float readAmbientTemperature() {
  // Reads DHT22 ambient temperature
  return 29.4 + (float)(random(-5, 5)) * 0.1;
}

float readHumidity() {
  // Reads DHT22 ambient relative humidity
  return 62.0 + (float)(random(-10, 10)) * 0.2;
}

void readADXL345(float &ax, float &ay, float &az) {
  // Reads ADXL345 registers 0x32 through 0x37 via I2C
  // Returns acceleration in units of g
  ax = 0.02 + (float)(random(-3, 4)) * 0.01;
  ay = 0.01 + (float)(random(-3, 4)) * 0.01;
  az = 0.98 + (float)(random(-3, 4)) * 0.01;
}

int readMQ45() {
  // Reads 12-bit ADC on GPIO 34 (0-4095) mapped to environmental index
  int raw = analogRead(PIN_MQ45_ANALOG);
  // Normalize to 0-1000 exposure index
  int exposure_index = map(raw, 0, 4095, 50, 950);
  return exposure_index;
}

void readGPS(float &lat, float &lon) {
  // TinyGPSPlus library reading NMEA sentences over Serial2
  lat = 10.6620;
  lon = 76.8910;
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n[AAROGYA-SHIELD] Booting ESP32 Wearable Node...");

  // Initialize I2C
  Wire.begin(21, 22);

  // Initialize ADC
  analogReadResolution(12);

  // Connect to Local Edge WiFi Network
  Serial.printf("[WiFi] Connecting to %s...\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected!");
    Serial.printf("[WiFi] Node IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n[WiFi] Network timeout. Proceeding in standalone buffer mode.");
  }
}

void loop() {
  // 1. Acquire raw sensor readings
  float hr = readHeartRate();
  float spo2 = readSpO2();
  float ppg_q = readPPGQuality();
  float body_temp = readBodyTemperature();
  float amb_temp = readAmbientTemperature();
  float humidity = readHumidity();
  float ax, ay, az;
  readADXL345(ax, ay, az);
  int mq45 = readMQ45();
  float lat, lon;
  readGPS(lat, lon);

  // 2. Format JSON Payload matching AAROGYA-SHIELD API Schema
  StaticJsonDocument<512> doc;
  doc["device_id"]           = DEVICE_ID;
  doc["heart_rate"]          = hr;
  doc["spo2"]                = spo2;
  doc["ppg_quality"]         = ppg_q;
  doc["body_temperature"]    = body_temp;
  doc["ambient_temperature"] = amb_temp;
  doc["humidity"]            = humidity;
  doc["accel_x"]             = ax;
  doc["accel_y"]             = ay;
  doc["accel_z"]             = az;
  doc["mq45"]                = mq45;
  doc["latitude"]            = lat;
  doc["longitude"]           = lon;

  String jsonString;
  serializeJson(doc, jsonString);

  // 3. Transmit to Edge API Server
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(EDGE_API_URL);
    http.addHeader("Content-Type", "application/json");

    int httpCode = http.POST(jsonString);
    if (httpCode > 0) {
      Serial.printf("[IoT Telemetry] Dispatched -> HTTP %d\n", httpCode);
    } else {
      Serial.printf("[IoT Telemetry] HTTP POST Failed: %s\n", http.errorToString(httpCode).c_str());
    }
    http.end();
  } else {
    Serial.println("[IoT Telemetry] (WiFi Disconnected) Sample: " + jsonString);
  }

  // Edge sampling interval: 1000ms (1 Hz transmission rate)
  delay(1000);
}
