@echo off
title VITALSYNC - Unified Health System Launcher
chcp 65001 >nul
cls

echo =====================================================================
echo   VITALSYNC: Unified Edge-AI Healthcare System
echo   - User POV Companion:     http://localhost:3000
echo   - Smartwatch Testing UI:  http://localhost:2134
echo   - FastAPI Edge Backend:   http://localhost:8000
echo =====================================================================
echo.

cd /d "%~dp0"

:: 1. Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    pause
    exit /b 1
)

:: 2. Check Node / npm
call npm --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js / npm is not installed or not in PATH!
    pause
    exit /b 1
)

:: 3. Free ports 8000, 2134, and 3000 from previous sessions
echo [*] Ensuring ports 8000, 2134, and 3000 are free...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /r ":8000.*LISTENING"') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /r ":2134.*LISTENING"') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /r ":3000.*LISTENING"') do taskkill /f /pid %%a >nul 2>&1

:: 4. Verify dependencies
if not exist "testing-ui\node_modules" (
    echo [*] Installing testing-ui dependencies (first run only)...
    cd /d "%~dp0testing-ui"
    call npm install
    cd /d "%~dp0"
)

if not exist "user-ui\node_modules" (
    echo [*] Installing user-ui dependencies (first run only)...
    cd /d "%~dp0user-ui"
    call npm install
    cd /d "%~dp0"
)

:: 5. Launch FastAPI Backend (Port 8000)
echo [*] Launching 1/3: FastAPI Backend Server (Port 8000)...
start "VITALSYNC Backend" cmd /c "title VITALSYNC Backend && cd /d "%~dp0" && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"

:: Wait for backend models to load
ping 127.0.0.1 -n 4 >nul

:: 6. Launch Smartwatch Testing UI (Port 2134)
echo [*] Launching 2/3: Smartwatch Testing UI (Port 2134)...
start "VITALSYNC Testing UI" cmd /c "title VITALSYNC Testing UI && cd /d "%~dp0testing-ui" && npm run dev"

:: 7. Launch User POV Companion UI (Port 3000)
echo [*] Launching 3/3: User Health Companion UI (Port 3000)...
start "VITALSYNC User UI" cmd /c "title VITALSYNC User UI && cd /d "%~dp0user-ui" && npm run dev"

:: Wait for Vite dev servers
ping 127.0.0.1 -n 4 >nul

:: 8. Open browsers
echo [*] Opening User POV Companion and Testing UI in browser...
start http://localhost:3000
start http://localhost:2134

echo.
echo =====================================================================
echo   VITALSYNC SERVICES ARE LIVE!
echo =====================================================================
echo   [USER POV]   Health Companion UI:  http://localhost:3000
echo   [TEST LAB]   Testing UI Console:   http://localhost:2134
echo   [BACKEND]    FastAPI Edge Engine:  http://localhost:8000
echo   [SWAGGER]    Interactive API Docs: http://localhost:8000/docs
echo   [WEBSOCKET]  Live Telemetry WS:    ws://localhost:8000/ws/live
echo =====================================================================
echo.
echo   Press any key in this window to STOP all services and exit...
pause >nul

echo.
echo [*] Shutting down all services...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /r ":8000.*LISTENING"') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /r ":2134.*LISTENING"') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /r ":3000.*LISTENING"') do taskkill /f /pid %%a >nul 2>&1
echo [OK] All services stopped cleanly.
ping 127.0.0.1 -n 2 >nul
exit /b 0
