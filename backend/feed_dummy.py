"""Pengirim data uji: meniru M2 yang mengirim tiap beberapa detik.

Contoh:
  python backend/feed_dummy.py                      # 3 node, tiap 10 detik
  python backend/feed_dummy.py --interval 3         # lebih cepat untuk demo
  python backend/feed_dummy.py --silent NODE-03     # NODE-03 tidak mengirim (uji "Data lama")
  python backend/feed_dummy.py --scenario panas     # sewaktu-waktu suhu tinggi dan debu pekat
"""
import argparse
import os
import random
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models import MockReceiverValidData

# (suhu, RH, tegangan debu) awal tiap node
BASE = {"NODE-01": (27.0, 58.0, 0.6), "NODE-02": (29.0, 48.0, 1.4), "NODE-03": (31.0, 40.0, 2.0)}
LIMIT = {"temp": (16.0, 40.0), "rh": (20.0, 85.0), "dust": (0.1, 3.4)}

ap = argparse.ArgumentParser()
ap.add_argument("--interval", type=float, default=10.0)
ap.add_argument("--silent", nargs="*", default=[], help="node yang tidak mengirim data")
ap.add_argument("--scenario", choices=["normal", "panas"], default="normal")
args = ap.parse_args()

state = {n: list(v) for n, v in BASE.items()}


def step(node: str, tick: int) -> tuple:
    t, rh, d = state[node]
    t = min(max(t + random.uniform(-0.4, 0.4), LIMIT["temp"][0]), LIMIT["temp"][1])
    rh = min(max(rh + random.uniform(-1.5, 1.5), LIMIT["rh"][0]), LIMIT["rh"][1])
    d = min(max(d + random.uniform(-0.15, 0.15), LIMIT["dust"][0]), LIMIT["dust"][1])
    if args.scenario == "panas" and (tick // 12) % 2 == 1:
        t, d = min(t + 0.8, 38.0), min(d + 0.2, 3.3)
    state[node] = [t, rh, d]
    return round(t, 1), round(rh, 1), round(d, 2)


db = SessionLocal()
print(f"Mengirim data tiap {args.interval:g} detik. Diam: {args.silent or '-'}. Ctrl+C untuk berhenti.")
tick = 0
try:
    while True:
        for n in BASE:
            if n in args.silent:
                continue
            t, rh, d = step(n, tick)
            db.add(MockReceiverValidData(
                node_id=n, temperature=t, humidity=rh, dust_raw_voltage=d,
                timestamp=datetime.now(timezone.utc), status_valid=True))
        db.commit()
        tick += 1
        time.sleep(args.interval)
except KeyboardInterrupt:
    pass
finally:
    db.close()
