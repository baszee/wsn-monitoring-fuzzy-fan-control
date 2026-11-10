"""Simulator lokal tabel M2 ``node_readings`` tanpa membutuhkan Orange Pi.

Contoh:
  $env:SENSOR_SOURCE="node_readings"
  python backend/tools/sim_node_readings.py --init --interval 5

Opsi --init hanya diizinkan untuk SQLite agar tidak membuat tabel di database
bersama milik M2 secara tidak sengaja.
"""

import argparse
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import random
import sys
import time


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal, engine  # noqa: E402
from app.sources.node_readings import NodeReading, SourceBase  # noqa: E402


def _sample(node_id: int, seq: int, rng: random.Random) -> NodeReading:
    phase = (seq % 120) / 120 * 2 * math.pi
    temperature = 27.0 + 2.5 * math.sin(phase) + (node_id - 2) * 0.5
    humidity = 52.0 - 5.0 * math.sin(phase) + (node_id - 2) * 1.5
    # Rentang dapat berada di bawah/atas asumsi offset 0,6 V; nilai nyata tetap
    # harus ditentukan dari pengujian sensor M2.
    v0 = max(0.0, min(3.4, 0.6 + 0.25 * node_id + 0.35 * (1 + math.sin(phase)) + rng.gauss(0, 0.02)))
    vpin = v0 / 1.5
    adc = max(0, min(4095, round(vpin / 3.3 * 4095)))
    dust = max(0.0, (v0 - 0.6) / 0.005)
    pressure = 1008.0 + 2.0 * math.sin(phase / 2)
    payload = (
        f"{node_id},{seq},{temperature:.2f},{humidity:.2f},{pressure:.2f},"
        f"{adc},{v0:.3f},{dust:.1f}"
    ).encode("ascii")
    return NodeReading(
        received_at=datetime.now(timezone.utc),
        node_id=node_id,
        seq=seq,
        adc=adc,
        vpin=round(vpin, 3),
        v0=round(v0, 3),
        dust_ugm3=round(dust, 1),
        temperature=round(temperature, 2),
        humidity=round(humidity, 2),
        pressure_hpa=round(pressure, 2),
        rssi=rng.randint(-105, -65),
        snr=round(rng.uniform(4.0, 10.0), 1),
        payload_raw=payload,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulator node_readings lokal")
    parser.add_argument("--init", action="store_true", help="buat tabel node_readings pada SQLite lokal")
    parser.add_argument("--once", action="store_true", help="tulis satu putaran lalu berhenti")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--nodes", type=int, nargs="+", default=[1, 2])
    args = parser.parse_args()

    if args.init:
        if engine.dialect.name != "sqlite":
            raise SystemExit("--init ditolak: hanya boleh membuat tabel pada SQLite lokal.")
        SourceBase.metadata.create_all(bind=engine)

    rng = random.Random(17)
    seq = {node_id: 0 for node_id in args.nodes}
    print(f"Simulator node_readings aktif pada {engine.url.render_as_string(hide_password=True)}")
    try:
        while True:
            with SessionLocal() as db:
                rows = []
                for node_id in args.nodes:
                    rows.append(_sample(node_id, seq[node_id], rng))
                    seq[node_id] = (seq[node_id] + 1) & 0xFFFF
                db.add_all(rows)
                db.commit()
                print(f"{datetime.now().isoformat(timespec='seconds')} menulis {len(rows)} node")
            if args.once:
                break
            time.sleep(max(args.interval, 0.1))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

