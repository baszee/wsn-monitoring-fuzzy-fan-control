@echo off
title WSNOVA - WSN Fuzzy Fan Control Server
cd /d "%~dp0"

echo ==========================================================
echo           MENJALANKAN SISTEM WSNOVA
echo ==========================================================
echo 1. Menerapkan migrasi dan konfigurasi awal database...
.venv\Scripts\python.exe backend\bootstrap_db.py
if errorlevel 1 (
    echo GAGAL: migrasi/bootstrap database tidak berhasil.
    exit /b 1
)

set "WSN_SENSOR_SOURCE=%SENSOR_SOURCE%"
set "WSN_WORKER_ENABLED=%WORKER_ENABLED%"
if exist ".env" if not defined WSN_SENSOR_SOURCE (
    for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"SENSOR_SOURCE=" ".env"') do set "WSN_SENSOR_SOURCE=%%B"
)
if exist ".env" if not defined WSN_WORKER_ENABLED (
    for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"WORKER_ENABLED=" ".env"') do set "WSN_WORKER_ENABLED=%%B"
)
if not defined WSN_SENSOR_SOURCE set "WSN_SENSOR_SOURCE=mock"
if not defined WSN_WORKER_ENABLED set "WSN_WORKER_ENABLED=true"
if /I "%WSN_WORKER_ENABLED%"=="false" (
    echo 2. Worker nonaktif; feed_dummy tidak dijalankan.
) else if /I not "%WSN_SENSOR_SOURCE%"=="mock" (
    echo 2. Sumber %WSN_SENSOR_SOURCE% aktif; feed_dummy tidak dijalankan.
) else (
    echo 2. Memulai simulator aliran sensor mock [feed_dummy]...
    start "WSNOVA Sensor Stream" /min cmd /c ".venv\Scripts\python.exe backend\feed_dummy.py --interval 5"
)

echo 3. Memulai server web dan API [Uvicorn]...
echo.
echo Dashboard aktif di: http://localhost:8000/dashboard/
echo Tekan Ctrl+C untuk menghentikan server.
echo ==========================================================
echo.
.venv\Scripts\uvicorn.exe backend.app.main:app --host 0.0.0.0 --port 8000 --reload

