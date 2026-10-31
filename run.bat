@echo off
title WSNOVA - WSN Fuzzy Fan Control Server
cd /d "%~dp0"

echo ==========================================================
echo           MENJALANKAN SISTEM WSNOVA
echo ==========================================================
echo 1. Memulai simulator aliran sensor (feed_dummy)...
start "WSNOVA Sensor Stream" /min cmd /c ".venv\Scripts\python.exe backend\feed_dummy.py --interval 5"

echo 2. Memulai server web & API (Uvicorn)...
echo.
echo Dashboard aktif di: http://localhost:8000/dashboard/
echo Tekan Ctrl+C untuk menghentikan server.
echo ==========================================================
echo.
.venv\Scripts\uvicorn.exe backend.app.main:app --host 0.0.0.0 --port 8000 --reload

