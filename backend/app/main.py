"""
Aplikasi Utama FastAPI (backend/app/main.py).
Subsistem Monitoring, Klasifikasi Kondisi, dan Kendali Fan DC 12V Berbasis Fuzzy Mamdani (WSN).
"""

import sys
from pathlib import Path

# Pastikan direktori backend masuk sys.path agar impor 'app.*' selalu berhasil
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.api import api_router
from app.services.worker import (
    background_worker_loop,
    run_processing_cycle,
    global_fan_controller,
)

# Event untuk menghentikan background worker secara rapi saat server shutdown
stop_event = asyncio.Event()
worker_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manajemen siklus hidup aplikasi FastAPI:
    - Startup: Memulai task background worker loop pemrosesan data sensor.
    - Shutdown: Menghentikan worker secara aman dan mereset driver PWM fan.
    """
    global worker_task, stop_event
    stop_event.clear()
    
    # Jalankan background worker periodik (tiap 5 detik)
    worker_task = asyncio.create_task(
        background_worker_loop(interval_seconds=5, stop_event=stop_event)
    )

    yield

    # Shutdown: Set stop event dan tunggu worker selesai
    stop_event.set()
    if worker_task:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    # Bersihkan state motor fan (reset ke 0.0%)
    global_fan_controller.driver.cleanup()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description=(
        "Backend API untuk monitoring kualitas lingkungan, klasifikasi kondisi "
        "(Baik, Perlu Perhatian, Buruk), dan pengendalian fan DC 12V "
        "menggunakan logika Fuzzy Mamdani murni NumPy pada Wireless Sensor Network."
    ),
    lifespan=lifespan
)

from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Konfigurasi Cross-Origin Resource Sharing (CORS) agar frontend dapat mengakses API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Memungkinkan akses dari Vite dev server (http://localhost:5173) & jaringan lokal
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Daftarkan Router REST API dengan prefix /api
app.include_router(api_router, prefix="/api")

# Sajikan landing page dan dashboard sebagai dua pengalaman yang terpisah.
frontend_path = Path(__file__).resolve().parent.parent.parent / "frontend"
src_path = frontend_path / "src"
dashboard_path = frontend_path / "dashboard"

if src_path.is_dir():
    app.mount("/src", StaticFiles(directory=str(src_path)), name="frontend_src")

if dashboard_path.is_dir():
    app.mount(
        "/dashboard",
        StaticFiles(directory=str(dashboard_path), html=True),
        name="dashboard",
    )


@app.get("/", tags=["Root"])
def root():
    """Landing page publik untuk memperkenalkan sistem."""
    return FileResponse(frontend_path / "index.html")


@app.get("/home", include_in_schema=False)
def home():
    """Alias landing page agar tautan /home tetap dapat digunakan."""
    return FileResponse(frontend_path / "index.html")


@app.get("/api/info", tags=["Root"])
def api_info():
    """Informasi status dasar aplikasi dan dokumentasi API."""
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "status": "online",
        "docs_url": "/docs",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/health", tags=["Root"])
def health_check():
    """Endpoint pengecekan kesehatan server backend."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/api/worker/tick", tags=["Worker"], summary="Picukan satu siklus pengolahan data manual")
def trigger_manual_tick(db: Session = Depends(get_db)):
    """Menjalankan satu siklus pengolahan data secara instan tanpa menunggu timer background."""
    result = run_processing_cycle(db=db)
    return {
        "status": "success",
        "cycle_id": result["processing_cycle_id"],
        "nodes_evaluated": result["nodes_evaluated"],
        "u_zona": result["zone_decision"]["zone_control_level"],
        "final_pwm": result["pwm_decision"]["final_pwm"]
    }
