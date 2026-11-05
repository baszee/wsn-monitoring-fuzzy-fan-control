@echo off
title WSNOVA - WSN Fuzzy Fan Control Server
cd /d "%~dp0"

echo ==========================================================
echo           MENJALANKAN SISTEM WSNOVA
echo ==========================================================
set "WSN_SENSOR_SOURCE=%SENSOR_SOURCE%"
if exist ".env" if not defined WSN_SENSOR_SOURCE (
    for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"SENSOR_SOURCE=" ".env"') do set "WSN_SENSOR_SOURCE=%%B"
)
if /I "%WSN_SENSOR_SOURCE%"=="node_readings" (
    echo 1. Sumber node_readings aktif; feed_dummy tidak dijalankan.
) else (
    echo 1. Memulai simulator aliran sensor mock (feed_dummy)...
    start "WSNOVA Sensor Stream" /min cmd /c ".venv\Scripts\python.exe backend\feed_dummy.py --interval 5"
)

echo 2. Memulai server web & API (Uvicorn)...
echo.
echo Dashboard aktif di: http://localhost:8000/dashboard/
echo Tekan Ctrl+C untuk menghentikan server.
echo ==========================================================
echo.
.venv\Scripts\uvicorn.exe backend.app.main:app --host 0.0.0.0 --port 8000 --reload

