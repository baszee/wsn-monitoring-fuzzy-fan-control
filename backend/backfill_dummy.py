"""Mengisi riwayat data uji yang halus dan masuk akal (default 24 jam, tiap 60 detik).

Dijalankan SEBELUM feed_dummy.py. Skrip ini MENGHAPUS data sensor, hasil fuzzy, dan
keputusan kendali yang ada, lalu membuat ulang lewat jalur perhitungan yang sama
dengan worker (fuzzy -> zona -> PWM dengan histeresis).

  python backend/backfill_dummy.py                 # 24 jam, tiap 60 detik
  python backend/backfill_dummy.py --hours 6 --step 30
"""
import argparse
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dummy_profile import PROFILE, Generator
from app.core.database import SessionLocal
from app.models import ControlConfig, FuzzyResult, MockReceiverValidData, ZoneControl, ZoneNode
from app.services.fuzzy import FuzzyMamdaniEngine, normalize_dust
from app.services.pwm import FanPWMController, MockPWMDriver
from app.services.zone import aggregate_zone

ap = argparse.ArgumentParser()
ap.add_argument("--hours", type=float, default=24.0)
ap.add_argument("--step", type=int, default=60, help="jarak antar data (detik)")
ap.add_argument("--zone", default="ZONA-1")
ap.add_argument("--seed", type=int, default=7)
args = ap.parse_args()

gen = Generator(args.seed)


db = SessionLocal()
config = db.query(ControlConfig).filter(ControlConfig.is_active == True).order_by(ControlConfig.created_at.desc()).first()
if not config:
    sys.exit("Konfigurasi aktif tidak ada. Jalankan seed_dummy.py dulu.")
nodes = db.query(ZoneNode).filter(ZoneNode.zone_id == args.zone, ZoneNode.is_active == True).all()
nodes = [n for n in nodes if n.node_id in PROFILE]
if not nodes:
    sys.exit("Node ZONA-1 tidak ditemukan. Jalankan seed_dummy.py dulu.")

print("Menghapus data lama...")
db.query(ZoneControl).delete()
db.query(FuzzyResult).delete()
db.query(MockReceiverValidData).delete()
db.commit()

engine = FuzzyMamdaniEngine(membership_params=config.membership_params, rule_base=config.rule_base)
ctrl = FanPWMController(driver=MockPWMDriver(initial_pwm=0.0), u_off=config.u_off, u_max=config.u_max,
                        d_min=config.d_min, delta_d_update=config.delta_d_update)

steps = int(args.hours * 3600 / args.step)
end = datetime.now(timezone.utc) - timedelta(seconds=args.step)
start = end - timedelta(seconds=args.step * (steps - 1))
print(f"Membuat {steps} siklus x {len(nodes)} node ({args.hours:g} jam, tiap {args.step} detik)...")

t0 = time.time()
us, on_steps, changes, last_pwm = [], 0, 0, None
for i in range(steps):
    ts = start + timedelta(seconds=args.step * i)
    local = ts.astimezone()
    hour = local.hour + local.minute / 60 + local.second / 3600
    cycle = f"HIS-{int(ts.timestamp())}-{uuid.uuid4().hex[:4]}"
    cands = []
    for zn in nodes:
        temp, rh, volt = gen.sample(zn.node_id, hour, args.step)
        rec = MockReceiverValidData(node_id=zn.node_id, temperature=temp, humidity=rh,
                                    dust_raw_voltage=volt, timestamp=ts, status_valid=True)
        db.add(rec)
        db.flush()
        d_idx = normalize_dust(volt, c_0=config.dust_low_reference, c_h=config.dust_high_reference)
        out = engine.evaluate(temperature=temp, humidity=rh, dust_index=d_idx)["outputs"]
        fr = FuzzyResult(zone_node_id=zn.zone_node_id, config_version=config.config_version,
                         processing_cycle_id=cycle, source_name="mock",
                         source_record_id=rec.id, source_timestamp=ts,
                         temperature=temp, humidity=rh, dust_raw_voltage=volt, dust_index=d_idx,
                         condition_score=out["condition_score"], condition_class=out["condition_class"],
                         control_level=out["control_level"], processed_at=ts)
        db.add(fr)
        db.flush()
        cands.append(dict(node_id=zn.node_id, zone_node_id=zn.zone_node_id, control_level=out["control_level"],
                          condition_score=out["condition_score"], condition_class=out["condition_class"],
                          source_timestamp=ts, source_record_id=rec.id, fuzzy_result_obj=fr))

    zone = aggregate_zone(node_results=cands, zone_id=args.zone, u_off=config.u_off)
    pwm = ctrl.compute_and_apply(u_zona=zone["zone_control_level"], has_valid_data=zone["has_valid_data"])
    det = zone.get("determining_result") or {}
    det_obj = det.get("fuzzy_result_obj")
    db.add(ZoneControl(
        config_version=config.config_version, processing_cycle_id=cycle, zone_id=args.zone,
        control_fuzzy_result_id=det_obj.fuzzy_result_id if det_obj else None,
        control_node_id=zone["determining_node_id"], zone_control_level=zone["zone_control_level"],
        pwm_command_percent=pwm["final_pwm"], candidate_pwm_percent=pwm["candidate_pwm"],
        previous_pwm_percent=pwm["previous_pwm"], auto_pwm_percent=pwm["final_pwm"],
        hysteresis_held=pwm["final_pwm"] != pwm["candidate_pwm"],
        control_status=zone["control_status"], fan_command_status=pwm["fan_command_status"],
        control_mode="auto", created_at=ts))

    us.append(zone["zone_control_level"] or 0.0)
    on_steps += pwm["final_pwm"] > 0
    changes += last_pwm is not None and pwm["final_pwm"] != last_pwm
    last_pwm = pwm["final_pwm"]
    if (i + 1) % 100 == 0:
        db.commit()
        print(f"  {i + 1}/{steps}  ({time.time() - t0:.0f} dtk)")
db.commit()
db.close()
print(f"Selesai dalam {time.time() - t0:.0f} dtk. u zona {min(us):.1f} sampai {max(us):.1f}; "
      f"fan menyala {100 * on_steps / steps:.0f}% waktu; perubahan PWM {changes} kali.")
print("Lanjutkan dengan: python backend/feed_dummy.py --interval 10")
