@echo off
title VITALSYNC - Edge-AI Health Monitoring System
chcp 65001 >nul
cls

echo =====================================================================
echo   VITALSYNC : Edge-AI Personal Health Monitoring System
echo   Smart Companion, Hardware Acquisition & Early-Warning Control Room
echo =====================================================================
echo.

:: Change directory to script folder
cd /d "%~dp0"

echo [*] Checking Python environment...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    pause
    exit /b 1
)

echo [*] Launching 1/3: FastAPI Edge Server (Port 8000)...
start "VITALSYNC - Backend Server" cmd /k "title VITALSYNC Backend && cd /d "%~dp0" && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

:: Brief delay to allow backend to bind port
timeout /t 3 /nobreak >nul

echo [*] Launching 2/3: ESP32 Hardware Emulator (1 Hz Telemetry)...
start "VITALSYNC - ESP32 Emulator" cmd /k "title VITALSYNC ESP32 Emulator && cd /d "%~dp0" && python firmware/esp32_hardware_emulator.py"

echo [*] Launching 3/3: Smartwatch Simulator UI (Port 2134)...
if exist "testing-ui\package.json" (
    start "VITALSYNC - Smartwatch UI" cmd /k "title VITALSYNC Smartwatch UI && cd /d "%~dp0testing-ui" && npm run dev"
)

:: Brief delay before launching browser
timeout /t 2 /nobreak >nul

echo [*] Opening VITALSYNC Control Room Dashboard...
start http://localhost:8000

echo.
echo =====================================================================
echo   ALL SERVICES STARTED SUCCESSFULLY!
echo =====================================================================
echo   - Control Room Dashboard:  http://localhost:8000
echo   - Smartwatch Testing UI:   http://localhost:2134
echo   - Interactive API Docs:    http://localhost:8000/docs
echo   - Live WebSocket Stream:   ws://localhost:8000/ws/live
echo =====================================================================
echo   To stop the services, close each opened service terminal window.
echo =====================================================================
echo.
pause
