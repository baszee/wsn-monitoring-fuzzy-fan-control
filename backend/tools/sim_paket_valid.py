"""Simulator lokal tabel penerima ``sesi_uji`` + ``paket_valid`` (schema.sql M2).

Meniru receiver.py: satu baris ``sesi_uji`` dibuat tiap simulator dijalankan, lalu
setiap putaran menulis satu paket valid per node dengan ``received_at`` eksplisit.

Contoh (SQLite lokal, tabel dibuat otomatis):
  $env:DATABASE_URL="sqlite:///./wsn_m2_dev.db"
  $env:SENSOR_SOURCE="paket_valid"
  python backend/tools/sim_paket_valid.py --init --interval 10

Contoh (PostgreSQL lokal milik sendiri yang sudah menjalankan schema.sql):
  python backend/tools/sim_paket_valid.py --allow-postgres --interval 10

Pengaman:
- ``--init`` hanya untuk SQLite; schema PostgreSQL wajib dibuat dari schema.sql M2.
- Menulis ke PostgreSQL harus diminta eksplisit dengan ``--allow-postgres``. Jangan
  memakainya pada database bersama tanpa persetujuan pemilik tabel penerima.
- Setiap sesi simulator diberi label berawalan ``SIM-WSNOVA`` agar mudah dibedakan.
"""

import argparse
from datetime import datetime, timezone
import math
from pathlib import Path
import random
import sys
import time


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal, engine  # noqa: E402
from app.sources.base import SourceBase  # noqa: E402
from app.sources.paket_valid import PaketValid, SesiUji  # noqa: E402


LABEL_PREFIX = "SIM-WSNOVA"


def _sample(sesi_uji_id: int, node_id: int, node_sesi: int, seq: int, rng: random.Random) -> PaketValid:
    phase = (seq % 120) / 120 * 2 * math.pi
    temperature = 27.0 + 2.5 * math.sin(phase) + (node_id - 2) * 0.5
    humidity = 52.0 - 5.0 * math.sin(phase) + (node_id - 2) * 1.5
    # Rentang v0 hanya ilustrasi; nilai nyata harus diambil dari sensor M2.
    v0 = max(0.0, min(3.4, 0.6 + 0.25 * node_id + 0.35 * (1 + math.sin(phase)) + rng.gauss(0, 0.02)))
    vpin = v0 / 1.5
    adc = max(0, min(4095, round(vpin / 3.3 * 4095)))
    dust = max(0.0, (v0 - 0.6) / 0.005)
    pressure = 1008.0 + 2.0 * math.sin(phase / 2)
    payload = (
        f"{node_id},{seq},{temperature:.2f},{humidity:.2f},{pressure:.2f},"
        f"{adc},{v0:.3f},{dust:.1f}"
    ).encode("ascii")
    return PaketValid(
        sesi_uji_id=sesi_uji_id,
        received_at=datetime.now(timezone.utc),
        node_id=node_id,
        sesi=node_sesi,
        seq=seq,
        adc=adc,
        vpin=round(vpin, 3),
        v0=round(v0, 3),
        temperature=round(temperature, 2),
        humidity=round(humidity, 2),
        pressure_hpa=round(pressure, 2),
        rssi=rng.randint(-105, -65),
        snr=round(rng.uniform(4.0, 10.0), 1),
        payload_raw=payload,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulator sesi_uji + paket_valid")
    parser.add_argument("--init", action="store_true", help="buat tabel penerima pada SQLite lokal")
    parser.add_argument("--allow-postgres", action="store_true",
                        help="izinkan menulis ke PostgreSQL (hanya database uji milik sendiri)")
    parser.add_argument("--once", action="store_true", help="tulis satu putaran lalu berhenti")
    parser.add_argument("--interval", type=float, default=10.0, help="detik antarputaran (default 10)")
    parser.add_argument("--nodes", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--mode", choices=("sensor", "uji"), default="sensor", help="mode sesi_uji")
    parser.add_argument("--label", default="", help="keterangan tambahan pada label sesi")
    parser.add_argument("--incomplete-every", type=int, default=0,
                        help="setiap N paket, kosongkan suhu (meniru BME280 gagal); 0 = tidak pernah")
    args = parser.parse_args()

    dialect = engine.dialect.name
    if args.init:
        if dialect != "sqlite":
            raise SystemExit("--init ditolak: hanya boleh membuat tabel pada SQLite lokal.")
        SourceBase.metadata.create_all(bind=engine)
    if dialect != "sqlite" and not args.allow_postgres:
        raise SystemExit(
            "Menulis ke PostgreSQL ditolak. Tambahkan --allow-postgres hanya bila ini "
            "database uji milik sendiri atau pemilik tabel penerima sudah setuju."
        )

    rng = random.Random(17)
    label = f"{LABEL_PREFIX} {datetime.now().isoformat(timespec='seconds')}"
    if args.label:
        label += f" | {args.label}"

    with SessionLocal() as db:
        sesi = SesiUji(
            mulai=datetime.now(timezone.utc),
            mode=args.mode,
            label=label,
            freq_hz=433_000_000,
            sf=9,
            bw_hz=125_000,
            cr_denom=5,
            tx_power_dbm=17,
            versi_paket=1,
        )
        db.add(sesi)
        db.commit()
        sesi_uji_id = sesi.id

    node_sesi = {node_id: rng.randint(1, 2**31 - 1) for node_id in args.nodes}
    seq = {node_id: 0 for node_id in args.nodes}
    count = 0
    print(f"Simulator paket_valid aktif pada {engine.url.render_as_string(hide_password=True)}")
    print(f"sesi_uji.id={sesi_uji_id} label='{label}' mode={args.mode}")
    try:
        while True:
            with SessionLocal() as db:
                rows = []
                for node_id in args.nodes:
                    row = _sample(sesi_uji_id, node_id, node_sesi[node_id], seq[node_id], rng)
                    count += 1
                    if args.incomplete_every and count % args.incomplete_every == 0:
                        row.temperature = None
                    rows.append(row)
                    seq[node_id] = (seq[node_id] + 1) & 0xFFFF
                db.add_all(rows)
                db.commit()
                print(f"{datetime.now().isoformat(timespec='seconds')} menulis {len(rows)} paket")
            if args.once:
                break
            time.sleep(max(args.interval, 0.1))
    except KeyboardInterrupt:
        pass
    finally:
        with SessionLocal() as db:
            row = db.get(SesiUji, sesi_uji_id)
            if row is not None:
                row.selesai = datetime.now(timezone.utc)
                db.commit()


if __name__ == "__main__":
    main()
