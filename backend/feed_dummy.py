import random
import time
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.models import MockReceiverValidData

NODES = ["NODE-01", "NODE-02", "NODE-03"]
INTERVAL = 10

db = SessionLocal()
print(f"Mengirim data tiap {INTERVAL} detik. Ctrl+C untuk berhenti.")
try:
    while True:
        for n in NODES:
            db.add(MockReceiverValidData(
                node_id=n,
                temperature=round(random.uniform(24, 36), 1),
                humidity=round(random.uniform(30, 75), 1),
                dust_raw_voltage=round(random.uniform(0.1, 3.0), 2),
                timestamp=datetime.now(timezone.utc),
                status_valid=True,
            ))
        db.commit()
        time.sleep(INTERVAL)
except KeyboardInterrupt:
    pass
finally:
    db.close()
