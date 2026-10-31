"""Pengirim data uji: meniru M2 yang mengirim tiap beberapa detik.
Memakai generator yang sama dengan backfill_dummy.py, jadi menyambung mulus dengan riwayat.

  python backend/feed_dummy.py                      # 3 node, tiap 10 detik
  python backend/feed_dummy.py --interval 3         # lebih cepat untuk demo
  python backend/feed_dummy.py --silent NODE-03     # NODE-03 tidak mengirim (uji "Data lama")
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dummy_profile import PROFILE, Generator
from app.core.database import SessionLocal
from app.models import MockReceiverValidData

ap = argparse.ArgumentParser()
ap.add_argument("--interval", type=float, default=10.0)
ap.add_argument("--silent", nargs="*", default=[], help="node yang tidak mengirim data")
args = ap.parse_args()

gen = Generator()
db = SessionLocal()
print(f"Mengirim data tiap {args.interval:g} detik. Diam: {args.silent or '-'}. Ctrl+C untuk berhenti.")
try:
    while True:
        now = datetime.now(timezone.utc)
        local = now.astimezone()
        hour = local.hour + local.minute / 60 + local.second / 3600
        for n in PROFILE:
            if n in args.silent:
                continue
            t, rh, d = gen.sample(n, hour, args.interval)
            db.add(MockReceiverValidData(node_id=n, temperature=t, humidity=rh, dust_raw_voltage=d,
                                         timestamp=now, status_valid=True))
        db.commit()
        time.sleep(args.interval)
except KeyboardInterrupt:
    pass
finally:
    db.close()
