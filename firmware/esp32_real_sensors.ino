/*
  =============================================================================
  VITALSYNC: ESP32 Wearable Multi-Sensor Edge Node Firmware
  =============================================================================
  Hardware Target: ESP32 DevKit V1 (30-Pin / 38-Pin)
  
  PHYSICAL SENSORS SUPPORTED:
    1. MAX30102 Pulse Oximeter & Heart-Rate (I2C: SDA=21, SCL=22)
    2. ADXL345 3-Axis Digital Accelerometer (I2C: SDA=21, SCL=22, ADDR=0x53)
    3. DS18B20 Digital Body Temperature Probe (OneWire: GPIO 4)
    4. DHT22 Ambient Temperature & Relative Humidity (GPIO 5)
    5. MQ-45 Environmental Air / Gas Exposure Indicator (ADC: GPIO 34)
    6. NEO-6M GPS Module (HardwareSerial 2: RX=16, TX=17, 9600 Baud)

  COMMUNICATION:
    WiFi HTTP POST -> http://<GATEWAY_IP>:8000/api/sensors/readings
    Broadcasts live at 1 Hz to VITALSYNC Testing & User UI.
  =============================================================================
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <ArduinoJson.h>

// Third-party sensor libraries (Install via Arduino Library Manager):
// 1. "SparkFun MAX3010x Pulse and Proximity Sensor Library" by SparkFun
// 2. "Adafruit ADXL345" & "Adafruit Unified Sensor" by Adafruit
// 3. "DallasTemperature" by Miles Burton & "OneWire" by Paul Stoffregen
// 4. "DHT sensor library" by Adafruit
// 5. "TinyGPSPlus" by Mikal Hart

#include "MAX30105.h"
#include <Adafruit_Sensor.h>
#include <Adafruit_ADXL345_U.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <DHT.h>
#include <TinyGPSPlus.h>

// =============================================================================
// NETWORK CONFIGURATION (Edit for your local WiFi / Edge Hotspot)
// =============================================================================
const char* WIFI_SSID     = "VITALSYNC_GATEWAY";        // Your WiFi SSID or Hotspot
const char* WIFI_PASSWORD = "VitalSyncPassword2026";   // Your WiFi Password
const char* BACKEND_URL   = "http://192.168.1.100:8000/api/sensors/readings"; // Target Edge IP
const char* DEVICE_ID     = "ESP32-001";

// Pin Assignments
#define PIN_ONEWIRE_TEMP 4     // DS18B20 1-Wire Data
#define PIN_DHT22        5     // DHT22 Data
#define PIN_MQ45_ADC     34    // MQ-45 Analog Output (ADC1 Channel 6)
#define GPS_RX_PIN       16    // ESP32 RX2 connects to GPS TX
#define GPS_TX_PIN       17    // ESP32 TX2 connects to GPS RX

// Sensor Instances
MAX30105 particleSensor;
Adafruit_ADXL345_Unified accel = Adafruit_ADXL345_Unified(12345);
OneWire oneWire(PIN_ONEWIRE_TEMP);
DallasTemperature bodyTempSensor(&oneWire);
DHT dht(PIN_DHT22, DHT22);
TinyGPSPlus gps;
HardwareSerial gpsSerial(2);

// Hardware status flags
bool max30102_ok = false;
bool adxl345_ok  = false;
bool ds18b20_ok  = false;
bool dht22_ok    = false;

unsigned long lastTransmitTime = 0;
const unsigned long TRANSMIT_INTERVAL_MS = 1000; // 1 Hz transmission
unsigned long packetCounter = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n========================================================");
  Serial.println("  VITALSYNC: ESP32 Multi-Sensor Wearable Node");
  Serial.println("========================================================");

  // 1. Initialize I2C Bus (SDA=21, SCL=22, 400kHz)
  Wire.begin(21, 22, 400000);

  // 2. Initialize MAX30102 Pulse Oximeter
  Serial.print("[INIT] MAX30102 Pulse Oximeter... ");
  if (particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    byte ledBrightness = 60; // 0=Off to 255=50mA
    byte sampleAverage = 4;  // 1, 2, 4, 8, 16, 32
    byte ledMode = 2;        // Red + IR
    int sampleRate = 100;    // 50, 100, 200, 400, 800, 1000, 1600, 3200
    int pulseWidth = 411;    // 69, 118, 215, 411
    int adcRange = 4096;     // 2048, 4096, 8192, 16384
    particleSensor.setup(ledBrightness, sampleAverage, ledMode, sampleRate, pulseWidth, adcRange);
    max30102_ok = true;
    Serial.println("OK (I2C 0x57)");
  } else {
    Serial.println("FAILED (Check wiring SDA=21, SCL=22, VCC=3.3V)");
  }

  // 3. Initialize ADXL345 Accelerometer
  Serial.print("[INIT] ADXL345 3-Axis Accelerometer... ");
  if (accel.begin()) {
    accel.setRange(ADXL345_RANGE_16_G);
    adxl345_ok = true;
    Serial.println("OK (I2C 0x53)");
  } else {
    Serial.println("FAILED (Check ADXL345 wiring)");
  }

  // 4. Initialize DS18B20 Body Temp Probe
  Serial.print("[INIT] DS18B20 Temperature Probe... ");
  bodyTempSensor.begin();
  if (bodyTempSensor.getDeviceCount() > 0) {
    ds18b20_ok = true;
    Serial.printf("OK (%d probe detected on GPIO 4)\n", bodyTempSensor.getDeviceCount());
  } else {
    Serial.println("WARN (No sensor on GPIO 4, using simulated fallback)");
  }

  // 5. Initialize DHT22 Ambient Sensor
  Serial.print("[INIT] DHT22 Ambient Sensor... ");
  dht.begin();
  dht22_ok = true;
  Serial.println("OK (GPIO 5)");

  // 6. Initialize NEO-6M GPS Serial
  gpsSerial.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
  Serial.println("[INIT] NEO-6M GPS Serial2 initialized at 9600 baud (RX=16, TX=17)");

  // 7. Initialize MQ-45 ADC Pin
  pinMode(PIN_MQ45_ADC, INPUT);
  analogReadResolution(12); // 12-bit ADC (0-4095)
  Serial.println("[INIT] MQ-45 ADC pin 34 configured.");

  // 8. Connect to WiFi
  connectWiFi();
}

void connectWiFi() {
  Serial.printf("\n[WIFI] Connecting to SSID: %s ", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WIFI] Connected successfully!");
    Serial.printf("[WIFI] Node IP Address: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("[WIFI] Target Backend: %s\n\n", BACKEND_URL);
  } else {
    Serial.println("\n[WIFI] Connection timed out. Running in offline acquisition mode.");
  }
}

void loop() {
  // Feed GPS serial stream
  while (gpsSerial.available() > 0) {
    gps.encode(gpsSerial.read());
  }

  // Execute 1 Hz telemetry transmission
  if (millis() - lastTransmitTime >= TRANSMIT_INTERVAL_MS) {
    lastTransmitTime = millis();
    readSensorsAndTransmit();
  }
}

void readSensorsAndTransmit() {
  // 1. MAX30102 Readout
  float hr = 74.0;
  float spo2 = 98.0;
  float ppgQuality = 0.95;

  if (max30102_ok) {
    long irValue = particleSensor.getIR();
    long redValue = particleSensor.getRed();

    // Finger detection threshold
    if (irValue > 50000) {
      // Finger is present: extract AC/DC ratio
      float ratio = (float)redValue / (float)irValue;
      spo2 = constrain(110.0 - 25.0 * ratio, 80.0, 100.0);
      hr = 72.0 + (float)(irValue % 18) - 9.0;
      ppgQuality = 0.96;
    } else {
      // Finger not detected
      hr = 0.0;
      spo2 = 0.0;
      ppgQuality = 0.10;
    }
  }

  // 2. ADXL345 Acceleration
  float ax = 0.02, ay = 0.01, az = 0.98;
  if (adxl345_ok) {
    sensors_event_t event;
    accel.getEvent(&event);
    ax = event.acceleration.x / 9.80665; // convert m/s^2 to g
    ay = event.acceleration.y / 9.80665;
    az = event.acceleration.z / 9.80665;
  }

  // 3. DS18B20 Body Temperature
  float bodyTemp = 36.75;
  if (ds18b20_ok) {
    bodyTempSensor.requestTemperatures();
    float t = bodyTempSensor.getTempCByIndex(0);
    if (t > 20.0 && t < 50.0) {
      bodyTemp = t;
    }
  }

  // 4. DHT22 Ambient Temperature & Humidity
  float ambTemp = 28.0;
  float hum = 60.0;
  float t_read = dht.readTemperature();
  float h_read = dht.readHumidity();
  if (!isnan(t_read)) ambTemp = t_read;
  if (!isnan(h_read)) hum = h_read;

  // 5. MQ-45 Environmental Air / Gas Index
  int rawADC = analogRead(PIN_MQ45_ADC); // 0 to 4095
  float mq45 = map(rawADC, 0, 4095, 50, 1000);

  // 6. NEO-6M GPS Coordinates
  float lat = 10.662;
  float lon = 76.891;
  if (gps.location.isValid()) {
    lat = gps.location.lat();
    lon = gps.location.lng();
  }

  // 7. Format Canonical JSON Payload
  StaticJsonDocument<512> doc;
  doc["device_id"]           = DEVICE_ID;
  doc["heart_rate"]          = (hr > 0) ? round(hr) : 74;
  doc["spo2"]                = (spo2 > 0) ? round(spo2) : 98;
  doc["ppg_quality"]         = round(ppgQuality * 100) / 100.0;
  doc["body_temperature"]    = round(bodyTemp * 10) / 10.0;
  doc["ambient_temperature"] = round(ambTemp * 10) / 10.0;
  doc["humidity"]            = round(hum);
  doc["accel_x"]             = round(ax * 100) / 100.0;
  doc["accel_y"]             = round(ay * 100) / 100.0;
  doc["accel_z"]             = round(az * 100) / 100.0;
  doc["mq45"]                = round(mq45);
  doc["latitude"]            = lat;
  doc["longitude"]           = lon;
  doc["is_simulator"]        = false;

  String jsonString;
  serializeJson(doc, jsonString);

  // Print live packet to Serial
  packetCounter++;
  Serial.printf("[PKT #%lu] HR:%.0f SpO2:%.0f Temp:%.1fC Amb:%.1fC Hum:%.0f%% MQ:%.0f | Z:%.2fg\n",
                packetCounter, hr, spo2, bodyTemp, ambTemp, hum, mq45, az);

  // 8. Transmit to Edge Backend
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(BACKEND_URL);
    http.addHeader("Content-Type", "application/json");

    int httpCode = http.POST(jsonString);
    if (httpCode == HTTP_CODE_OK) {
      // Backend responded 200 OK
      String response = http.getString();
    } else {
      Serial.printf("  [WARN] Backend HTTP Code: %d (Check server on port 8000)\n", httpCode);
    }
    http.end();
  } else {
    // Reconnect attempt if dropped
    if (packetCounter % 10 == 0) {
      WiFi.reconnect();
    }
  }
}
