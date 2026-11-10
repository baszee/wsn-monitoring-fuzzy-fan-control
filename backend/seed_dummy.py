"""
Skrip Seeder Dummy untuk Basis Data Subsistem Monitoring & Kontrol Fan WSN.
Menyediakan data inisialisasi:
1. control_config (konfigurasi v1.0.0, 27 aturan fuzzy Mamdani, parameter MFs)
2. zone_nodes (pendaftaran 3 node pada 'ZONA-1')
3. mock_receiver_valid_data (sampel data sensor valid: kondisi normal, panas-kering, pekat-debu)
"""

import sys
import os
from datetime import datetime, timezone, timedelta

# Pastikan direktori backend masuk sys.path saat dieksekusi langsung
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text

from app.core.database import APP_SCHEMA, SessionLocal, engine, Base
from app.models import ZoneNode, ControlConfig, MockReceiverValidData

def get_default_fuzzy_membership_params():
    """Definisi parameter fungsi keanggotaan trapesium dan segitiga sesuai PRD."""
    return {
        "temp": {
            "Rendah": {"type": "trapmf", "params": [0.0, 0.0, 16.0, 18.0]},
            "Normal": {"type": "trapmf", "params": [16.0, 18.0, 30.0, 32.0]},
            "Tinggi": {"type": "trapmf", "params": [30.0, 32.0, 50.0, 50.0]},
        },
        "rh": {
            "Kering": {"type": "trapmf", "params": [0.0, 0.0, 35.0, 40.0]},
            "Normal": {"type": "trapmf", "params": [35.0, 40.0, 60.0, 65.0]},
            "Lembap": {"type": "trapmf", "params": [60.0, 65.0, 100.0, 100.0]},
        },
        "dust": {
            "Rendah": {"type": "trapmf", "params": [0.0, 0.0, 0.20, 0.40]},
            "Sedang": {"type": "trimf", "params": [0.20, 0.50, 0.80]},
            "Tinggi": {"type": "trapmf", "params": [0.60, 0.80, 1.0, 1.0]},
        },
        "condition_score": {
            "Baik": {"type": "trapmf", "params": [0.0, 0.0, 20.0, 40.0]},
            "Perlu Perhatian": {"type": "trimf", "params": [30.0, 50.0, 70.0]},
            "Buruk": {"type": "trapmf", "params": [60.0, 80.0, 100.0, 100.0]},
        },
        "control_level": {
            "Mati": {"type": "trapmf", "params": [0.0, 0.0, 5.0, 15.0]},
            "Rendah": {"type": "trimf", "params": [10.0, 30.0, 50.0]},
            "Sedang": {"type": "trimf", "params": [40.0, 60.0, 80.0]},
            "Tinggi": {"type": "trapmf", "params": [70.0, 85.0, 100.0, 100.0]},
        }
    }

def get_default_rule_base():
    """27 Aturan Fuzzy Mamdani (Debu x RH x Suhu -> Skor Kondisi & Tingkat Kendali)."""
    return [
        # --- DEBU RENDAH ---
        {"id": 1, "dust": "Rendah", "rh": "Kering", "temp": "Rendah", "condition_class": "Buruk", "control_level": "Mati"},
        {"id": 2, "dust": "Rendah", "rh": "Kering", "temp": "Normal", "condition_class": "Perlu Perhatian", "control_level": "Mati"},
        {"id": 3, "dust": "Rendah", "rh": "Kering", "temp": "Tinggi", "condition_class": "Buruk", "control_level": "Rendah"},
        {"id": 4, "dust": "Rendah", "rh": "Normal", "temp": "Rendah", "condition_class": "Perlu Perhatian", "control_level": "Mati"},
        {"id": 5, "dust": "Rendah", "rh": "Normal", "temp": "Normal", "condition_class": "Baik", "control_level": "Mati"},
        {"id": 6, "dust": "Rendah", "rh": "Normal", "temp": "Tinggi", "condition_class": "Perlu Perhatian", "control_level": "Rendah"},
        {"id": 7, "dust": "Rendah", "rh": "Lembap", "temp": "Rendah", "condition_class": "Buruk", "control_level": "Rendah"},
        {"id": 8, "dust": "Rendah", "rh": "Lembap", "temp": "Normal", "condition_class": "Perlu Perhatian", "control_level": "Rendah"},
        {"id": 9, "dust": "Rendah", "rh": "Lembap", "temp": "Tinggi", "condition_class": "Buruk", "control_level": "Sedang"},

        # --- DEBU SEDANG ---
        {"id": 10, "dust": "Sedang", "rh": "Kering", "temp": "Rendah", "condition_class": "Buruk", "control_level": "Sedang"},
        {"id": 11, "dust": "Sedang", "rh": "Kering", "temp": "Normal", "condition_class": "Perlu Perhatian", "control_level": "Sedang"},
        {"id": 12, "dust": "Sedang", "rh": "Kering", "temp": "Tinggi", "condition_class": "Buruk", "control_level": "Tinggi"},
        {"id": 13, "dust": "Sedang", "rh": "Normal", "temp": "Rendah", "condition_class": "Perlu Perhatian", "control_level": "Sedang"},
        {"id": 14, "dust": "Sedang", "rh": "Normal", "temp": "Normal", "condition_class": "Perlu Perhatian", "control_level": "Sedang"},
        {"id": 15, "dust": "Sedang", "rh": "Normal", "temp": "Tinggi", "condition_class": "Perlu Perhatian", "control_level": "Tinggi"},
        {"id": 16, "dust": "Sedang", "rh": "Lembap", "temp": "Rendah", "condition_class": "Buruk", "control_level": "Tinggi"},
        {"id": 17, "dust": "Sedang", "rh": "Lembap", "temp": "Normal", "condition_class": "Perlu Perhatian", "control_level": "Tinggi"},
        {"id": 18, "dust": "Sedang", "rh": "Lembap", "temp": "Tinggi", "condition_class": "Buruk", "control_level": "Tinggi"},

        # --- DEBU TINGGI ---
        {"id": 19, "dust": "Tinggi", "rh": "Kering", "temp": "Rendah", "condition_class": "Buruk", "control_level": "Tinggi"},
        {"id": 20, "dust": "Tinggi", "rh": "Kering", "temp": "Normal", "condition_class": "Buruk", "control_level": "Tinggi"},
        {"id": 21, "dust": "Tinggi", "rh": "Kering", "temp": "Tinggi", "condition_class": "Buruk", "control_level": "Tinggi"},
        {"id": 22, "dust": "Tinggi", "rh": "Normal", "temp": "Rendah", "condition_class": "Buruk", "control_level": "Tinggi"},
        {"id": 23, "dust": "Tinggi", "rh": "Normal", "temp": "Normal", "condition_class": "Buruk", "control_level": "Tinggi"},
        {"id": 24, "dust": "Tinggi", "rh": "Normal", "temp": "Tinggi", "condition_class": "Buruk", "control_level": "Tinggi"},
        {"id": 25, "dust": "Tinggi", "rh": "Lembap", "temp": "Rendah", "condition_class": "Buruk", "control_level": "Tinggi"},
        {"id": 26, "dust": "Tinggi", "rh": "Lembap", "temp": "Normal", "condition_class": "Buruk", "control_level": "Tinggi"},
        {"id": 27, "dust": "Tinggi", "rh": "Lembap", "temp": "Tinggi", "condition_class": "Buruk", "control_level": "Tinggi"},
    ]

def seed_database(include_samples: bool = True):
    print("=== Memulai Inisialisasi & Seeding Data Dummy ===")
    
    # Schema khusus WSNova (opsional, hanya PostgreSQL). Nama sudah divalidasi
    # di app.core.config sehingga aman disisipkan sebagai identifier.
    if APP_SCHEMA:
        print(f"Memastikan schema '{APP_SCHEMA}' untuk tabel WSNova tersedia...")
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{APP_SCHEMA}"'))

    # Buat seluruh tabel aplikasi jika belum ada. Tabel milik penerima (paket_valid,
    # sesi_uji, node_readings) berada di metadata terpisah dan tidak pernah dibuat di sini.
    print("Membuat tabel database via SQLAlchemy metadata...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 1. Seeding control_config
        config_version = "v1.0.0"
        existing_config = db.query(ControlConfig).filter_by(config_version=config_version).first()
        if not existing_config:
            print(f"Menambahkan konfigurasi fuzzy & kontrol '{config_version}'...")
            config = ControlConfig(
                config_version=config_version,
                membership_params=get_default_fuzzy_membership_params(),
                rule_base=get_default_rule_base(),
                dust_low_reference=0.05,
                dust_high_reference=3.50,
                u_off=15.0,
                u_max=88.33,
                d_min=30.0,
                delta_d_update=5.0,
                is_active=True
            )
            db.add(config)
        else:
            print(f"Konfigurasi '{config_version}' sudah tersedia.")

        # 2. Seeding zone_nodes
        nodes_to_register = [
            ("ZONA-1", "NODE-01"),
            ("ZONA-1", "NODE-02"),
            ("ZONA-1", "NODE-03"),
        ]
        for zone_id, node_id in nodes_to_register:
            existing_node = db.query(ZoneNode).filter_by(zone_id=zone_id, node_id=node_id).first()
            if not existing_node:
                print(f"Mendaftarkan {node_id} pada {zone_id}...")
                db.add(ZoneNode(zone_id=zone_id, node_id=node_id, is_active=True))
            else:
                print(f"Node {node_id} pada {zone_id} sudah terdaftar.")

        # 3. Data contoh hanya ditambahkan saat skrip seeder dijalankan manual.
        # Bootstrap produksi memanggil fungsi ini tanpa data contoh agar setiap
        # restart tidak menggandakan riwayat pengukuran.
        sample_records = []
        if include_samples:
            now = datetime.now(timezone.utc)
            sample_records = [
            # Kondisi Normal (NODE-01): Suhu nyaman, RH ideal, debu sangat rendah
            {
                "node_id": "NODE-01",
                "temperature": 24.5,
                "humidity": 52.0,
                "dust_raw_voltage": 0.12,
                "timestamp": now - timedelta(seconds=20),
                "status_valid": True
            },
            # Kondisi Panas & Kering (NODE-02): Suhu tinggi, RH rendah, debu sedang
            {
                "node_id": "NODE-02",
                "temperature": 34.2,
                "humidity": 28.0,
                "dust_raw_voltage": 0.35,
                "timestamp": now - timedelta(seconds=15),
                "status_valid": True
            },
            # Kondisi Pekat Debu (NODE-03): Suhu hangat, RH normal, debu pekat mendekati acuan tinggi
            {
                "node_id": "NODE-03",
                "temperature": 27.8,
                "humidity": 56.5,
                "dust_raw_voltage": 2.85,
                "timestamp": now - timedelta(seconds=10),
                "status_valid": True
            },
            # Rekaman historis tambahan untuk simulasi time-series
            {
                "node_id": "NODE-01",
                "temperature": 24.2,
                "humidity": 51.5,
                "dust_raw_voltage": 0.10,
                "timestamp": now - timedelta(minutes=5),
                "status_valid": True
            },
            {
                "node_id": "NODE-02",
                "temperature": 33.8,
                "humidity": 29.0,
                "dust_raw_voltage": 0.30,
                "timestamp": now - timedelta(minutes=5),
                "status_valid": True
            },
            {
                "node_id": "NODE-03",
                "temperature": 27.5,
                "humidity": 55.0,
                "dust_raw_voltage": 2.70,
                "timestamp": now - timedelta(minutes=5),
                "status_valid": True
            }
            ]

            print("Menyisipkan data sampel ke tabel mock_receiver_valid_data...")
            for row in sample_records:
                mock_entry = MockReceiverValidData(**row)
                db.add(mock_entry)

        db.commit()
        print("=== Seeding Berhasil Diselesaikan! ===")

    except Exception as e:
        db.rollback()
        print(f"Terjadi kesalahan saat seeding: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
