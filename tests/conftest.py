"""Konfigurasi pytest untuk isolasi pengujian otomatis dari hardware & database luar.

Memastikan saat pytest berjalan:
- PWM_DRIVER dipaksa 'mock' (tidak membuka COM port hardware Arduino)
- DATABASE_URL diarahkan ke SQLite in-memory (tidak menghubungi Supabase / DB luar)
- SENSOR_SOURCE disetel ke 'mock'
- Schema DB dikosongkan (SQLite)
"""
import os
import sys
from pathlib import Path

# Pasang direktori backend ke sys.path sebelum modul backend dimuat
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Paksa environment test sebelum modul app diimpor
os.environ["PWM_DRIVER"] = "mock"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SENSOR_SOURCE"] = "mock"
os.environ["APP_DB_SCHEMA"] = ""
os.environ["SOURCE_DB_SCHEMA"] = ""
os.environ["WORKER_ENABLED"] = "false"
