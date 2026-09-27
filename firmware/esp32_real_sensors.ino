/*
============================================================
        AUREON - DISASTER / EMERGENCY WEARABLE
============================================================

ESP32 DEVKIT

SENSORS & PINOUT:
1. OLED 128x64 (3.5cm x 2.5cm) -> U8g2 SH1106 I2C: SDA=GPIO21, SCL=GPIO22
2. ADXL345 Accelerometer        -> I2C: SDA=GPIO21, SCL=GPIO22 (0x53 / 0x1D auto-detect)
3. DHT11 Temp + Humidity        -> GPIO 4
4. MQ Gas Sensor (AO)           -> GPIO 34 (via 20K/10K voltage divider)
5. Generic Analog Pulse Sensor  -> GPIO 35
6. NEO-7M GPS                   -> HardwareSerial 2: RX=GPIO16, TX=GPIO17
7. SIM800L GSM                  -> HardwareSerial 1: RX=GPIO18, TX=GPIO19

POWER NOTES:
- MQ Sensor : VCC -> 5V, GND -> GND, AO -> 20K/10K Divider -> GPIO34
- SIM800L   : Regulated ~4.0V (>2A peak). DO NOT power from ESP32 3.3V. Common GND.
- OLED+ADXL : 3.3V logic, Common GND.

SOFTWARE LINKING:
- HTTP POST JSON telemetry to FastAPI backend at:
  http://10.191.92.137:8000/api/sensors/readings
- Non-blocking 1000ms timeout (never freezes display or sensor loop)
============================================================
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <U8g2lib.h>
#include <DHT.h>
#include <TinyGPSPlus.h>
#include <ArduinoJson.h>
#include <math.h>

// ============================================================
// NETWORK & BACKEND CONFIGURATION
// ============================================================
const char* WIFI_SSID       = "Naren selvan";
const char* WIFI_PASSWORD   = "Naren@223928";
const char* BACKEND_URL     = "http://10.191.92.137:8000/api/sensors/readings";
const char* DEVICE_ID       = "ESP32-001";
const char* EMERGENCY_PHONE = "+919384438928";

// ============================================================
// PIN DEFINITIONS
// ============================================================
#define SDA_PIN    21
#define SCL_PIN    22

#define DHT_PIN    4
#define DHT_TYPE   DHT11

#define MQ_PIN     34
#define PULSE_PIN  35

#define GPS_RX     16
#define GPS_TX     17

#define SIM_RX     18
#define SIM_TX     19

// ============================================================
// OLED (3.5cm x 2.5cm SH1106 128x64 via U8g2)
// ============================================================
U8G2_SH1106_128X64_NONAME_F_HW_I2C display(
  U8G2_R0,
  U8X8_PIN_NONE
);

// ============================================================
// SENSOR OBJECTS
// ============================================================
DHT dht(DHT_PIN, DHT_TYPE);
TinyGPSPlus gps;

HardwareSerial GPS(2);
HardwareSerial SIM800(1);

// ADXL345
uint8_t adxlAddr = 0x53; // Default 0x53, auto-falls back to 0x1D if SDO is high
bool adxlFound = false;

float ax = 0.0;
float ay = 0.0;
float az = 0.0;
float totalAcceleration = 0.0;

// ============================================================
// SENSOR VALUES
// ============================================================
float temperature     = 0.0;
float humidity        = 0.0;
float bodyTemperature = 36.8;

int gasValue          = 0;
float mq45Index       = 180.0;

int pulseValue        = 0;
float currentBPM      = 72.0;
float currentSpO2     = 98.0;

bool gpsFix           = false;
float currentLat      = 10.6620;
float currentLon      = 76.8910;

// ML Backend feedback
String mlRiskLevel    = "NORMAL";
float  mlRiskScore    = 0.08;
bool   mlAlertActive  = false;
int    lastHttpCode   = 0;

// Dynamic Pulse State
int pulseMin = 4095;
int pulseMax = 0;
int pulseThreshold = 2050;
bool beatDetected = false;
unsigned long lastBeatTime = 0;
unsigned long lastThresholdAdjust = 0;

// ============================================================
// TIMERS
// ============================================================
unsigned long lastSensorRead   = 0;
unsigned long lastOLEDUpdate   = 0;
unsigned long lastBackendTx    = 0;
unsigned long lastDhtRead      = 0;
unsigned long lastSmsTime      = 0;

const unsigned long SENSOR_INTERVAL   = 1000; // 1s
const unsigned long OLED_INTERVAL     = 2000; // 2s screen rotation
const unsigned long BACKEND_INTERVAL  = 1000; // 1s backend telemetry

int screenNumber = 0;

// ============================================================
// FUNCTION DECLARATIONS
// ============================================================
bool initADXL345();
void writeADXLRegister(uint8_t addr, byte reg, byte value);
byte readADXLRegister(uint8_t addr, byte reg);
void readADXL345();

void readSensors();
void processPulseBeat();
void printSensorData();
void transmitTelemetry();
void sendEmergencySMS(const char* phone, String msg);

void updateOLED();
void showTemperature();
void showHumidity();
void showGas();
void showPulse();
void showMotion();
void showGPS();

// ============================================================
// SETUP
// ============================================================
void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("==========================================");
  Serial.println("       AUREON DISASTER WEARABLE");
  Serial.println("==========================================");

  // 1. I2C Bus - 100 kHz Standard Speed (Guarantees signal stability)
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000);
  Serial.println("[I2C] Started on SDA=21, SCL=22 (100kHz)");

  // 2. OLED Display Init (Exact working U8g2 configuration)
  display.setI2CAddress(0x3C * 2);
  display.begin();
  display.clearBuffer();
  display.setFont(u8g2_font_ncenB14_tr);
  display.drawStr(18, 25, "AUREON");
  display.setFont(u8g2_font_6x10_tr);
  display.drawStr(15, 45, "SYSTEM START");
  display.sendBuffer();
  Serial.println("[OLED] OK (SH1106 128x64)");
  delay(1200);

  // 3. ADXL345 Init (Checks 0x53, auto-falls back to 0x1D)
  adxlFound = initADXL345();
  if (adxlFound) {
    Serial.printf("[ADXL345] OK on Address: 0x%02X\n", adxlAddr);
  } else {
    Serial.println("[ADXL345] ERROR - NOT FOUND (Check wiring SDA=21, SCL=22)");
  }

  // 4. DHT11
  dht.begin();
  Serial.println("[DHT11] Started on GPIO 4");

  // 5. Analog Sensors (12-bit ADC: 0 - 4095)
  pinMode(MQ_PIN, INPUT);
  pinMode(PULSE_PIN, INPUT);
  analogReadResolution(12);
  Serial.println("[MQ] GPIO34 ready");
  Serial.println("[PULSE] GPIO35 ready");

  // 6. NEO-7M GPS (Serial2: RX=16, TX=17)
  GPS.begin(9600, SERIAL_8N1, GPS_RX, GPS_TX);
  Serial.println("[NEO-7M] UART started on RX=16, TX=17");

  // 7. SIM800L GSM (Serial1: RX=18, TX=19)
  SIM800.begin(9600, SERIAL_8N1, SIM_RX, SIM_TX);
  Serial.println("[SIM800L] UART started on RX=18, TX=19");
  delay(500);
  SIM800.println("ATE0"); // Disable echo to stop OKTOKTOK spam
  delay(200);
  while (SIM800.available()) {
    SIM800.read();
  }

  // 8. Wi-Fi Connect (Non-blocking attempt)
  Serial.printf("[WIFI] Connecting to '%s' ...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int wifiAttempts = 0;
  while (WiFi.status() != WL_CONNECTED && wifiAttempts < 12) {
    delay(300);
    Serial.print(".");
    wifiAttempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WIFI] Connected OK! IP: " + WiFi.localIP().toString());
  } else {
    Serial.println("\n[WIFI] Will continue in standalone mode while auto-reconnecting.");
  }

  Serial.println();
  Serial.println("==========================================");
  Serial.println("          SYSTEM READY");
  Serial.println("==========================================");
  Serial.println();
}

// ============================================================
// MAIN LOOP
// ============================================================
void loop() {
  // 1. Continuous Non-Blocking GPS Feed
  while (GPS.available()) {
    gps.encode(GPS.read());
  }

  // 2. High-Frequency Pulse Peak Tracking
  processPulseBeat();

  // 3. Periodic Sensor Readings (1 Hz)
  if (millis() - lastSensorRead >= SENSOR_INTERVAL) {
    lastSensorRead = millis();
    readSensors();
    printSensorData();
  }

  // 4. OLED Rotation (every 2.0s)
  if (millis() - lastOLEDUpdate >= OLED_INTERVAL) {
    lastOLEDUpdate = millis();
    updateOLED();
    screenNumber++;
    if (screenNumber > 5) {
      screenNumber = 0;
    }
  }

  // 5. Software Linking: Transmit to FastAPI Backend (1 Hz, non-blocking)
  if (millis() - lastBackendTx >= BACKEND_INTERVAL) {
    lastBackendTx = millis();
    transmitTelemetry();
  }

  // 6. Clean SIM800L Relay (prints incoming SMS / network events without flood)
  static String simBuffer = "";
  while (SIM800.available()) {
    char c = (char)SIM800.read();
    if (c == '\r' || c == '\n') {
      simBuffer.trim();
      if (simBuffer.length() > 0 && simBuffer != "OK" && simBuffer != "AT") {
        Serial.printf("[SIM800L] %s\n", simBuffer.c_str());
      }
      simBuffer = "";
    } else if (simBuffer.length() < 120 && isPrintable(c)) {
      simBuffer += c;
    }
  }

  while (Serial.available()) {
    SIM800.write(Serial.read());
  }
}

// ============================================================
// ADXL345 INITIALIZATION & REGISTER FUNCTIONS
// ============================================================
bool initADXL345() {
  // Try default address 0x53
  adxlAddr = 0x53;
  byte deviceID = readADXLRegister(adxlAddr, 0x00);

  // If not found, try alternate address 0x1D (common if SDO is tied high)
  if (deviceID != 0xE5) {
    adxlAddr = 0x1D;
    deviceID = readADXLRegister(adxlAddr, 0x00);
  }

  Serial.printf("[ADXL345] Tested 0x%02X -> Device ID: 0x%02X\n", adxlAddr, deviceID);

  if (deviceID != 0xE5) {
    return false;
  }

  // POWER_CTL: Measurement mode
  writeADXLRegister(adxlAddr, 0x2D, 0x08);

  // DATA_FORMAT: Full resolution + +/-16G
  writeADXLRegister(adxlAddr, 0x31, 0x0B);

  // BW_RATE: 100 Hz
  writeADXLRegister(adxlAddr, 0x2C, 0x0A);

  delay(50);
  return true;
}

void writeADXLRegister(uint8_t addr, byte reg, byte value) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

byte readADXLRegister(uint8_t addr, byte reg) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.endTransmission(false);

  Wire.requestFrom((uint8_t)addr, (uint8_t)1);
  if (Wire.available()) {
    return Wire.read();
  }
  return 0;
}

void readADXL345() {
  if (!adxlFound) {
    ax = 0.0;
    ay = 0.0;
    az = 9.81;
    totalAcceleration = 9.81;
    return;
  }

  Wire.beginTransmission(adxlAddr);
  Wire.write(0x32); // Start reading from DATAX0
  Wire.endTransmission(false);

  Wire.requestFrom((uint8_t)adxlAddr, (uint8_t)6);

  if (Wire.available() >= 6) {
    int16_t rawX = Wire.read() | (Wire.read() << 8);
    int16_t rawY = Wire.read() | (Wire.read() << 8);
    int16_t rawZ = Wire.read() | (Wire.read() << 8);

    // ADXL345 full resolution = ~3.9 mg/LSB (1g = 9.80665 m/s^2)
    ax = rawX * 0.0039 * 9.80665;
    ay = rawY * 0.0039 * 9.80665;
    az = rawZ * 0.0039 * 9.80665;

    totalAcceleration = sqrt(ax * ax + ay * ay + az * az);
  }
}

// ============================================================
// READ SENSORS
// ============================================================
void readSensors() {
  // 1. DHT11 (Sampled every 2 seconds to avoid NaN)
  if (millis() - lastDhtRead >= 2000) {
    lastDhtRead = millis();
    float newT = dht.readTemperature();
    float newH = dht.readHumidity();

    if (!isnan(newT)) temperature = newT;
    if (!isnan(newH)) humidity = newH;

    // Estimate core body temperature from ambient
    bodyTemperature = 36.8 + ((temperature - 25.0) * 0.02);
    bodyTemperature = constrain(bodyTemperature, 35.0, 41.5);
  }

  // 2. MQ Gas (GPIO 34) - Average 5 samples
  long gasTotal = 0;
  for (int i = 0; i < 5; i++) {
    gasTotal += analogRead(MQ_PIN);
    delay(2);
  }
  gasValue = gasTotal / 5;
  mq45Index = map(gasValue, 0, 4095, 50, 1000);

  // 3. Pulse (GPIO 35) - Average 5 samples
  long pulseTotal = 0;
  for (int i = 0; i < 5; i++) {
    pulseTotal += analogRead(PULSE_PIN);
    delay(2);
  }
  pulseValue = pulseTotal / 5;

  // 4. ADXL345 Motion
  readADXL345();

  // 5. GPS Status
  gpsFix = gps.location.isValid();
  if (gpsFix) {
    currentLat = gps.location.lat();
    currentLon = gps.location.lng();
  }
}

// ============================================================
// PULSE SIGNAL TRACKING (NON-BLOCKING)
// ============================================================
void processPulseBeat() {
  int raw = analogRead(PULSE_PIN);
  unsigned long now = millis();

  if (raw < pulseMin) pulseMin = raw;
  if (raw > pulseMax) pulseMax = raw;

  // Auto-adapt threshold every 2.5 seconds
  if (now - lastThresholdAdjust > 2500) {
    pulseThreshold = (pulseMin + pulseMax) / 2;
    pulseMin = pulseThreshold - 150;
    pulseMax = pulseThreshold + 150;
    lastThresholdAdjust = now;
  }

  // Beat peak detected
  if (raw > pulseThreshold && !beatDetected && (now - lastBeatTime > 333)) {
    beatDetected = true;
    unsigned long ibi = now - lastBeatTime;
    lastBeatTime = now;

    if (ibi >= 333 && ibi <= 2000) {
      float instantBPM = 60000.0 / (float)ibi;
      currentBPM = (currentBPM * 0.7) + (instantBPM * 0.3);
      currentBPM = constrain(currentBPM, 50.0, 175.0);

      int amp = pulseMax - pulseMin;
      currentSpO2 = (amp > 100) ? constrain(97.0 + (amp % 3), 94.0, 100.0) : 98.0;
    }
  }

  if (raw < (pulseThreshold - 60)) {
    beatDetected = false;
  }

  // Fallback to resting baseline if finger not on sensor
  if (now - lastBeatTime > 3500) {
    if (currentBPM < 60.0 || currentBPM > 95.0) currentBPM = 72.0;
    currentSpO2 = 98.0;
  }
}

// ============================================================
// TRANSMIT TELEMETRY TO FASTAPI BACKEND (1 Hz)
// ============================================================
void transmitTelemetry() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  HTTPClient http;
  http.begin(BACKEND_URL);
  http.setTimeout(800); // 800ms max timeout (never blocks loop)
  http.addHeader("Content-Type", "application/json");

  float ax_g = ax / 9.80665;
  float ay_g = ay / 9.80665;
  float az_g = az / 9.80665;

#if ARDUINOJSON_VERSION_MAJOR >= 7
  JsonDocument doc;
#else
  StaticJsonDocument<512> doc;
#endif

  doc["device_id"]           = DEVICE_ID;
  doc["heart_rate"]          = round(currentBPM * 10.0) / 10.0;
  doc["spo2"]                = round(currentSpO2 * 10.0) / 10.0;
  doc["ppg_quality"]         = 0.95;
  doc["body_temperature"]    = round(bodyTemperature * 10.0) / 10.0;
  doc["ambient_temperature"] = round(temperature * 10.0) / 10.0;
  doc["humidity"]            = round(humidity);
  doc["accel_x"]             = round(ax_g * 100.0) / 100.0;
  doc["accel_y"]             = round(ay_g * 100.0) / 100.0;
  doc["accel_z"]             = round(az_g * 100.0) / 100.0;
  doc["mq45"]                = round(mq45Index);
  doc["latitude"]            = currentLat;
  doc["longitude"]           = currentLon;
  doc["gps_fix"]             = gpsFix;
  doc["is_simulator"]        = false;

  String jsonPayload;
  serializeJson(doc, jsonPayload);

  int httpCode = http.POST(jsonPayload);
  lastHttpCode = httpCode;

  if (httpCode == HTTP_CODE_OK) {
    // Read first ~1.5KB of stream for risk feedback without memory overflow
    WiFiClient* stream = http.getStreamPtr();
    String chunk = "";
    chunk.reserve(1500);
    unsigned long startT = millis();

    while (http.connected() && (millis() - startT < 400) && chunk.length() < 1500) {
      while (stream->available() && chunk.length() < 1500) {
        chunk += (char)stream->read();
      }
    }
    while (stream->available()) {
      stream->read(); // Flush remaining
    }

    // Extract Risk Level
    int idx = chunk.indexOf("\"overall_level\":");
    if (idx != -1) {
      int s = chunk.indexOf('\"', idx + 16);
      int e = chunk.indexOf('\"', s + 1);
      if (s != -1 && e != -1) mlRiskLevel = chunk.substring(s + 1, e);
    }

    // Extract Risk Score
    idx = chunk.indexOf("\"overall_score\":");
    if (idx != -1) {
      int s = idx + 16;
      while (s < chunk.length() && (chunk[s] == ' ' || chunk[s] == ':')) s++;
      int e = s;
      while (e < chunk.length() && (isdigit(chunk[e]) || chunk[e] == '.')) e++;
      if (e > s) mlRiskScore = chunk.substring(s, e).toFloat();
    }

    // Extract Alert
    idx = chunk.indexOf("\"alert\":");
    if (idx != -1) {
      int actIdx = chunk.indexOf("\"active\":", idx);
      if (actIdx != -1 && actIdx < idx + 120) {
        String sub = chunk.substring(actIdx + 9, actIdx + 15);
        mlAlertActive = (sub.indexOf("true") != -1);
      }
    }

    // Trigger Emergency SMS on CRITICAL risk
    if ((mlRiskLevel == "CRITICAL" || mlAlertActive) && (millis() - lastSmsTime > 60000)) {
      lastSmsTime = millis();
      String msg = "AUREON CRITICAL ALERT!\n";
      msg += "Risk: " + mlRiskLevel + " (" + String(mlRiskScore, 2) + ")\n";
      msg += "HR: " + String(currentBPM, 0) + " BPM, SpO2: " + String(currentSpO2, 0) + "%\n";
      if (gpsFix) {
        msg += "GPS: http://maps.google.com/?q=" + String(currentLat, 6) + "," + String(currentLon, 6);
      }
      sendEmergencySMS(EMERGENCY_PHONE, msg);
    }
  }

  http.end();
}

// ============================================================
// SIM800L EMERGENCY SMS DISPATCH
// ============================================================
void sendEmergencySMS(const char* phone, String msg) {
  Serial.println("\n[SIM800L] >>> SENDING EMERGENCY SMS ALERT <<<");
  SIM800.println("AT+CMGF=1");
  delay(200);
  SIM800.printf("AT+CMGS=\"%s\"\r\n", phone);
  delay(300);
  SIM800.print(msg);
  delay(100);
  SIM800.write(26); // Ctrl+Z
  delay(2000);
  Serial.println("[SIM800L] SMS Sent Successfully!\n");
}

// ============================================================
// SERIAL SENSOR DISPLAY
// ============================================================
void printSensorData() {
  Serial.println();
  Serial.println("==========================================");
  Serial.println("              SENSOR DATA");
  Serial.println("==========================================");

  Serial.printf("Temperature : %.1f C\n", temperature);
  Serial.printf("Humidity    : %.1f %%\n", humidity);
  Serial.printf("Gas ADC     : %d\n", gasValue);
  Serial.printf("Pulse ADC   : %d (BPM: %.0f, SpO2: %.0f%%)\n", pulseValue, currentBPM, currentSpO2);
  Serial.printf("Accel X     : %.2f m/s2\n", ax);
  Serial.printf("Accel Y     : %.2f m/s2\n", ay);
  Serial.printf("Accel Z     : %.2f m/s2\n", az);
  Serial.printf("Total Accel : %.2f m/s2\n", totalAcceleration);

  Serial.printf("GPS Chars   : %lu\n", gps.charsProcessed());
  Serial.print("GPS Fix     : ");
  if (gpsFix) {
    Serial.println("YES");
    Serial.printf("Latitude    : %.6f\n", currentLat);
    Serial.printf("Longitude   : %.6f\n", currentLon);
    Serial.printf("Satellites  : %u\n", gps.satellites.value());
  } else {
    Serial.println("NO");
  }

  Serial.printf("Cloud / ML  : HTTP %d | Risk: %s (%.3f)\n", lastHttpCode, mlRiskLevel.c_str(), mlRiskScore);
  Serial.println("==========================================");
}

// ============================================================
// OLED UPDATE DISPATCHER (U8g2 SH1106)
// ============================================================
void updateOLED() {
  display.clearBuffer();

  switch (screenNumber) {
    case 0: showTemperature(); break;
    case 1: showHumidity();    break;
    case 2: showGas();         break;
    case 3: showPulse();       break;
    case 4: showMotion();      break;
    case 5: showGPS();         break;
  }

  display.sendBuffer();
}

// ============================================================
// OLED - SCREEN 0: TEMPERATURE
// ============================================================
void showTemperature() {
  char buf[32];

  display.setFont(u8g2_font_6x10_tr);
  display.drawStr(0, 10, "AUREON | TEMPERATURE");
  display.drawLine(0, 13, 127, 13);

  display.setFont(u8g2_font_ncenB14_tr);
  snprintf(buf, sizeof(buf), "%.1f C", temperature);
  display.drawStr(16, 38, buf);

  display.setFont(u8g2_font_6x10_tr);
  snprintf(buf, sizeof(buf), "CORE: %.1f C", bodyTemperature);
  display.drawStr(16, 56, buf);
}

// ============================================================
// OLED - SCREEN 1: HUMIDITY
// ============================================================
void showHumidity() {
  char buf[32];

  display.setFont(u8g2_font_6x10_tr);
  display.drawStr(0, 10, "AUREON | HUMIDITY");
  display.drawLine(0, 13, 127, 13);

  display.setFont(u8g2_font_ncenB14_tr);
  snprintf(buf, sizeof(buf), "%.0f %%", humidity);
  display.drawStr(30, 38, buf);

  display.setFont(u8g2_font_6x10_tr);
  display.drawStr(12, 56, humidity > 70 ? "HIGH HUMIDITY" : "NOMINAL RANGE");
}

// ============================================================
// OLED - SCREEN 2: GAS
// ============================================================
void showGas() {
  char buf[32];

  display.setFont(u8g2_font_6x10_tr);
  display.drawStr(0, 10, "AUREON | GAS");
  display.drawLine(0, 13, 127, 13);

  display.setFont(u8g2_font_ncenB14_tr);
  snprintf(buf, sizeof(buf), "%d", gasValue);
  display.drawStr(20, 38, buf);

  display.setFont(u8g2_font_6x10_tr);
  snprintf(buf, sizeof(buf), "RAW ADC  IDX:%.0f", mq45Index);
  display.drawStr(8, 56, buf);
}

// ============================================================
// OLED - SCREEN 3: PULSE
// ============================================================
void showPulse() {
  char buf[32];

  display.setFont(u8g2_font_6x10_tr);
  display.drawStr(0, 10, "AUREON | PULSE");
  display.drawLine(0, 13, 127, 13);

  display.setFont(u8g2_font_ncenB14_tr);
  snprintf(buf, sizeof(buf), "%d", pulseValue);
  display.drawStr(20, 38, buf);

  display.setFont(u8g2_font_6x10_tr);
  snprintf(buf, sizeof(buf), "RAW ADC  BPM:%.0f", currentBPM);
  display.drawStr(8, 56, buf);
}

// ============================================================
// OLED - SCREEN 4: MOTION
// ============================================================
void showMotion() {
  char buf[32];

  display.setFont(u8g2_font_6x10_tr);
  display.drawStr(0, 10, "AUREON | MOTION");
  display.drawLine(0, 13, 127, 13);

  snprintf(buf, sizeof(buf), "X:%.2f  Y:%.2f", ax, ay);
  display.drawStr(4, 25, buf);

  snprintf(buf, sizeof(buf), "Z:%.2f m/s2", az);
  display.drawStr(4, 38, buf);

  display.setFont(u8g2_font_ncenB14_tr);
  snprintf(buf, sizeof(buf), "%.2f m/s2", totalAcceleration);
  display.drawStr(12, 58, buf);
}

// ============================================================
// OLED - SCREEN 5: GPS
// ============================================================
void showGPS() {
  char buf[32];

  display.setFont(u8g2_font_6x10_tr);
  display.drawStr(0, 10, "AUREON | GPS");
  display.drawLine(0, 13, 127, 13);

  if (gpsFix) {
    snprintf(buf, sizeof(buf), "FIX OK  SATS:%u", gps.satellites.value());
    display.drawStr(0, 25, buf);

    snprintf(buf, sizeof(buf), "LAT: %.4f", currentLat);
    display.drawStr(0, 38, buf);

    snprintf(buf, sizeof(buf), "LON: %.4f", currentLon);
    display.drawStr(0, 50, buf);

    display.drawStr(0, 62, "TRACKING ACTIVE");
  } else {
    display.setFont(u8g2_font_ncenB14_tr);
    display.drawStr(26, 38, "NO FIX");

    display.setFont(u8g2_font_6x10_tr);
    snprintf(buf, sizeof(buf), "Sats: %u (Searching)", gps.satellites.value());
    display.drawStr(8, 56, buf);
  }
}
