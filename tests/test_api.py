"""
Unit Test untuk REST API FastAPI dan Worker Pemrosesan (tests/test_api.py).
Dapat dijalankan langsung dengan `python tests/test_api.py` atau melalui `pytest`.

Menguji:
1. Health check & root endpoint
2. POST /api/fuzzy/simulate (simulasi What-If tanpa database/efek fan)
3. Pipeline Worker dengan database SQLite in-memory
4. GET /api/nodes/latest
5. GET /api/control/latest
6. GET /api/fuzzy/{node_id}/detail
"""

import sys
import os
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Tambahkan backend ke sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.database import Base, get_db
from app.models import (
    ControlConfig,
    ZoneNode,
    MockReceiverValidData,
    FuzzyResult,
    ZoneControl
)
from app.services.fuzzy import (
    DEFAULT_MEMBERSHIP_PARAMS,
    DEFAULT_RULE_BASE
)
from app.services.worker import run_processing_cycle
from app.services.pwm import FanPWMController, MockPWMDriver
from app.main import app

# Siapkan database SQLite in-memory untuk pengujian independen
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Override dependency get_db di FastAPI
app.dependency_overrides[get_db] = override_get_db


class TestAPIAndWorker:
    """Rangkaian pengujian endpoint API dan pipeline siklus pengolahan data."""

    def setup_method(self):
        """Buat skema tabel dan data awal sebelum setiap metode uji."""
        Base.metadata.create_all(bind=test_engine)
        self.db = TestingSessionLocal()

        # Seed konfigurasi v1.0.0
        self.config = ControlConfig(
            config_version="v1.0.0",
            membership_params=DEFAULT_MEMBERSHIP_PARAMS,
            rule_base=DEFAULT_RULE_BASE,
            dust_low_reference=0.05,
            dust_high_reference=3.50,
            u_off=15.0,
            u_max=88.33,
            d_min=30.0,
            delta_d_update=5.0,
            is_active=True
        )
        self.db.add(self.config)

        # Seed 3 node di ZONA-1
        self.node1 = ZoneNode(zone_id="ZONA-1", node_id="NODE-01", is_active=True)
        self.node2 = ZoneNode(zone_id="ZONA-1", node_id="NODE-02", is_active=True)
        self.node3 = ZoneNode(zone_id="ZONA-1", node_id="NODE-03", is_active=True)
        self.db.add_all([self.node1, self.node2, self.node3])

        # Seed data sensor dummy
        now = datetime.now(timezone.utc)
        self.sensor_records = [
            # NODE-01: Normal (T=24, RH=50, V=0.10)
            MockReceiverValidData(
                node_id="NODE-01",
                temperature=24.0,
                humidity=50.0,
                dust_raw_voltage=0.10,
                timestamp=now - timedelta(seconds=10),
                status_valid=True
            ),
            # NODE-02: Panas & Kering (T=34, RH=28, V=0.35)
            MockReceiverValidData(
                node_id="NODE-02",
                temperature=34.0,
                humidity=28.0,
                dust_raw_voltage=0.35,
                timestamp=now - timedelta(seconds=8),
                status_valid=True
            ),
            # NODE-03: Sangat Pekat Debu (T=27, RH=55, V=3.20) -> Harus menjadi node penentu i*
            MockReceiverValidData(
                node_id="NODE-03",
                temperature=27.0,
                humidity=55.0,
                dust_raw_voltage=3.20,
                timestamp=now - timedelta(seconds=5),
                status_valid=True
            ),
        ]
        self.db.add_all(self.sensor_records)
        self.db.commit()

    def teardown_method(self):
        """Hapus seluruh tabel setelah uji selesai."""
        self.db.close()
        Base.metadata.drop_all(bind=test_engine)

    def test_simulate_endpoint_pure_logic(self):
        """Uji fungsi endpoint /api/fuzzy/simulate tanpa efek fisik."""
        from app.api.endpoints import simulate_fuzzy
        from app.schemas import FuzzySimulateRequest

        # Simulasi kondisi dingin & kering
        req = FuzzySimulateRequest(
            temperature=12.0,
            humidity=25.0,
            dust_raw=0.08,
            include_curves=True
        )
        res = simulate_fuzzy(req)
        assert res.outputs["condition_class"] == "Buruk"
        assert res.outputs["control_level"] <= 15.0
        assert res.curves is not None
        assert len(res.curves["universe"]) == 1001

    def test_worker_processing_cycle(self):
        """Uji eksekusi penuh pipeline worker pemrosesan dan penyimpanan DB."""
        mock_driver = MockPWMDriver()
        controller = FanPWMController(driver=mock_driver)

        # Jalankan satu siklus pengolahan data
        res = run_processing_cycle(db=self.db, controller=controller)

        assert res["nodes_evaluated"] == 3
        assert res["config_version"] == "v1.0.0"
        
        # NODE-03 memiliki debu pekat, sehingga harus menjadi penentu i*
        assert res["zone_decision"]["determining_node_id"] == "NODE-03"
        assert res["zone_decision"]["zone_control_level"] >= 80.0
        assert res["pwm_decision"]["final_pwm"] >= 90.0
        assert res["pwm_decision"]["fan_command_status"] == "Aktif"

        # Verifikasi data tersimpan di tabel fuzzy_results
        fuzzy_rows = self.db.query(FuzzyResult).all()
        assert len(fuzzy_rows) == 3

        # Verifikasi data tersimpan di tabel zone_controls
        ctrl_rows = self.db.query(ZoneControl).all()
        assert len(ctrl_rows) == 1
        assert ctrl_rows[0].control_node_id == "NODE-03"
        assert ctrl_rows[0].fan_command_status == "Aktif"

    def test_get_nodes_latest(self):
        """Uji endpoint GET /api/nodes/latest."""
        from app.api.endpoints import get_latest_nodes

        # Jalankan worker terlebih dahulu agar ada hasil perhitungan
        run_processing_cycle(db=self.db)

        nodes = get_latest_nodes(db=self.db)
        assert len(nodes) == 3

        # Cari NODE-03 dan pastikan is_determining_node = True
        node3 = next(n for n in nodes if n.node_id == "NODE-03")
        assert node3.is_determining_node is True
        assert node3.condition_class == "Buruk"
        assert node3.temperature == 27.0

        # NODE-01 tidak boleh menjadi node penentu
        node1 = next(n for n in nodes if n.node_id == "NODE-01")
        assert node1.is_determining_node is False

    def test_get_node_history(self):
        """Uji endpoint riwayat menggunakan data aktual tanpa interpolasi."""
        from app.api.endpoints import get_node_history

        rows = get_node_history(node_id="NODE-03", range="24h", db=self.db)

        assert len(rows) == 1
        assert rows[0]["node_id"] == "NODE-03"
        assert rows[0]["temperature"] == 27.0
        assert 0.0 <= rows[0]["dust_index"] <= 1.0

    def test_get_control_latest(self):
        """Uji endpoint GET /api/control/latest."""
        from app.api.endpoints import get_latest_control

        # Jalankan worker
        run_processing_cycle(db=self.db)

        ctrl = get_latest_control(db=self.db)
        assert ctrl.zone_id == "ZONA-1"
        assert ctrl.determining_node_id == "NODE-03"
        assert ctrl.fan_command_status == "Aktif"
        assert ctrl.pwm_command_percent >= 90.0

    def test_get_fuzzy_detail(self):
        """Uji endpoint GET /api/fuzzy/{node_id}/detail."""
        from app.api.endpoints import get_fuzzy_node_detail

        detail = get_fuzzy_node_detail(node_id="NODE-01", db=self.db)
        assert detail.node_id == "NODE-01"
        assert detail.inputs["temperature"] == 24.0
        assert "Normal" in detail.memberships["temperature"]
        assert len(detail.active_rules) > 0
        assert detail.curves is not None


if __name__ == "__main__":
    print("=== Menjalankan Unit Test FastAPI & Worker ===")
    test_instance = TestAPIAndWorker()
    methods = [m for m in dir(test_instance) if m.startswith("test_")]

    total_passed = 0
    total_tests = 0

    for method_name in methods:
        total_tests += 1
        test_instance.setup_method()
        test_method = getattr(test_instance, method_name)
        try:
            test_method()
            print(f"  [PASS] {method_name}")
            total_passed += 1
        except Exception as e:
            print(f"  [FAIL] {method_name}: {e}")
            raise
        finally:
            test_instance.teardown_method()

    print(f"\n==========================================")
    print(f"Hasil: {total_passed}/{total_tests} Pengujian API & Worker Lolos 100%!")
    print(f"==========================================")
