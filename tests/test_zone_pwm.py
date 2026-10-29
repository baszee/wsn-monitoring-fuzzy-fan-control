"""
Unit Test untuk Agregasi Zona dan Pemetaan PWM Fan (tests/test_zone_pwm.py).
Dapat dijalankan langsung dengan `python tests/test_zone_pwm.py` atau melalui `pytest`.

Memverifikasi:
1. Agregasi zona: max u_i, penentuan i*, penanganan V(t) kosong.
2. Aturan tie-break deterministik: waktu data terbaru lalu node_id terkecil.
3. Pemetaan sinyal PWM: batasan u_off, u_max, D_min, dan clipping [0, 100%].
4. Histeresis delta_d_update: start seketika dari 0%, penahanan fluktuasi kecil, dan mati langsung 0%.
5. Mock PWM Driver: pencatatan riwayat perintah dan proteksi batas.
"""

import sys
import os
from datetime import datetime, timezone, timedelta

# Fallback untuk pytest jika dijalankan mandiri
try:
    import pytest
except ImportError:
    class MockPytest:
        @staticmethod
        def approx(expected, rel=None, abs_tol=1e-2, **kwargs):
            tol = kwargs.get("abs", abs_tol)
            class ApproxVal:
                def __init__(self, val, tolerance):
                    self.val = val
                    self.tol = tolerance
                def __eq__(self, other):
                    diff = self.val - other
                    return (diff if diff >= 0 else -diff) <= self.tol
                def __repr__(self):
                    return f"approx({self.val} +/- {self.tol})"
            return ApproxVal(expected, tol)

        @staticmethod
        def raises(expected_exc):
            class RaisesContext:
                def __enter__(self):
                    return self
                def __exit__(self, exc_type, exc_val, exc_tb):
                    if exc_type is None:
                        raise AssertionError(f"Expected exception {expected_exc.__name__} was not raised.")
                    return issubclass(exc_type, expected_exc)
            return RaisesContext()

    pytest = MockPytest()

# Tambahkan backend ke sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.zone import aggregate_zone
from app.services.pwm import (
    calculate_candidate_pwm,
    apply_hysteresis,
    MockPWMDriver,
    FanPWMController
)


class TestZoneAggregation:
    """Pengujian logika agregasi zona dan penentuan node penentu i*."""

    def test_empty_node_set(self):
        """Kasus V(t) kosong: kendali tidak tersedia."""
        res = aggregate_zone([], zone_id="ZONA-1")
        assert res["has_valid_data"] is False
        assert res["zone_control_level"] is None
        assert res["determining_node_id"] is None
        assert res["control_status"] == "Kendali tidak tersedia"
        assert res["fan_command_status"] == "Kendali tidak tersedia"
        assert res["total_nodes_evaluated"] == 0

    def test_single_node(self):
        """Satu node valid menentukan kendali zona."""
        now = datetime.now(timezone.utc)
        nodes = [
            {"node_id": "NODE-01", "control_level": 42.5, "source_timestamp": now}
        ]
        res = aggregate_zone(nodes, zone_id="ZONA-1")
        assert res["has_valid_data"] is True
        assert res["zone_control_level"] == 42.5
        assert res["determining_node_id"] == "NODE-01"
        assert res["control_status"] == "Aktif"
        assert res["fan_command_status"] == "Aktif"

    def test_multiple_nodes_distinct_max(self):
        """Memilih node dengan u_i tertinggi (worst-case)."""
        now = datetime.now(timezone.utc)
        nodes = [
            {"node_id": "NODE-01", "control_level": 25.0, "source_timestamp": now},
            {"node_id": "NODE-02", "control_level": 78.4, "source_timestamp": now},  # Pemenang
            {"node_id": "NODE-03", "control_level": 55.2, "source_timestamp": now},
        ]
        res = aggregate_zone(nodes, zone_id="ZONA-1")
        assert res["zone_control_level"] == 78.4
        assert res["determining_node_id"] == "NODE-02"

    def test_tie_break_by_timestamp(self):
        """Jika nilai u_i sama, pilih data dengan timestamp terbaru."""
        base_time = datetime.now(timezone.utc)
        nodes = [
            {"node_id": "NODE-01", "control_level": 60.0, "source_timestamp": base_time - timedelta(seconds=30)},
            {"node_id": "NODE-02", "control_level": 60.0, "source_timestamp": base_time},  # Lebih baru
        ]
        res = aggregate_zone(nodes, zone_id="ZONA-1")
        assert res["zone_control_level"] == 60.0
        assert res["determining_node_id"] == "NODE-02"

    def test_tie_break_by_node_id(self):
        """Jika nilai u_i dan timestamp sama, pilih node_id terkecil (alfabetis)."""
        same_time = datetime.now(timezone.utc)
        nodes = [
            {"node_id": "NODE-03", "control_level": 50.0, "source_timestamp": same_time},
            {"node_id": "NODE-01", "control_level": 50.0, "source_timestamp": same_time},  # Terkecil
            {"node_id": "NODE-02", "control_level": 50.0, "source_timestamp": same_time},
        ]
        res = aggregate_zone(nodes, zone_id="ZONA-1")
        assert res["zone_control_level"] == 50.0
        assert res["determining_node_id"] == "NODE-01"

    def test_zone_below_u_off(self):
        """Jika semua node memiliki u_i <= u_off (15.0), status perintah fan adalah 'Mati'."""
        now = datetime.now(timezone.utc)
        nodes = [
            {"node_id": "NODE-01", "control_level": 5.42, "source_timestamp": now},
            {"node_id": "NODE-02", "control_level": 12.0, "source_timestamp": now},
        ]
        res = aggregate_zone(nodes, zone_id="ZONA-1", u_off=15.0)
        assert res["zone_control_level"] == 12.0
        assert res["determining_node_id"] == "NODE-02"
        assert res["control_status"] == "Mati"
        assert res["fan_command_status"] == "Mati"


class TestPWMCalculation:
    """Pengujian rumus pemetaan D_baru dari u_zona."""

    def test_pwm_null_and_below_u_off(self):
        assert calculate_candidate_pwm(None) == 0.0
        assert calculate_candidate_pwm(0.0) == 0.0
        assert calculate_candidate_pwm(14.99) == 0.0
        assert calculate_candidate_pwm(15.0) == 0.0

    def test_pwm_at_minimum_turn_on(self):
        # Tepat di atas u_off -> mendekati D_min (30%)
        pwm = calculate_candidate_pwm(15.01, u_off=15.0, u_max=88.33, d_min=30.0)
        assert pwm == pytest.approx(30.0, abs=0.1)

    def test_pwm_at_u_max(self):
        # Pada u_max (88.33) -> harus tepat 100%
        pwm = calculate_candidate_pwm(88.33, u_off=15.0, u_max=88.33, d_min=30.0)
        assert pwm == 100.0

    def test_pwm_above_u_max_clipped(self):
        # Melebihi u_max harus di-clip ke 100%
        pwm = calculate_candidate_pwm(95.0, u_off=15.0, u_max=88.33, d_min=30.0)
        assert pwm == 100.0

    def test_pwm_linear_midpoint(self):
        # Titik tengah antara u_off (15.0) dan u_max (88.33) -> ratio 0.5
        # PWM = 30 + 0.5 * (100 - 30) = 65.0%
        mid_u = 15.0 + 0.5 * (88.33 - 15.0)
        pwm = calculate_candidate_pwm(mid_u, u_off=15.0, u_max=88.33, d_min=30.0)
        assert pwm == pytest.approx(65.0, abs=0.05)


class TestHysteresisLogic:
    """Pengujian aturan penahanan histeresis delta_d_update."""

    def test_start_from_zero_pwm(self):
        """Transisi dari 0% ke aktif langsung diterapkan tanpa histeresis."""
        d_final, updated = apply_hysteresis(
            d_candidate=35.0,
            d_prev=0.0,
            is_off_condition=False,
            delta_d_update=5.0
        )
        assert d_final == 35.0
        assert updated is True

    def test_small_change_maintained(self):
        """Perubahan < delta_d_update (5%) harus menahan nilai sebelumnya."""
        # Perubahan naik 3% (50% -> 53%)
        d_final, updated = apply_hysteresis(
            d_candidate=53.0,
            d_prev=50.0,
            is_off_condition=False,
            delta_d_update=5.0
        )
        assert d_final == 50.0
        assert updated is False

        # Perubahan turun 4% (50% -> 46%)
        d_final, updated = apply_hysteresis(
            d_candidate=46.0,
            d_prev=50.0,
            is_off_condition=False,
            delta_d_update=5.0
        )
        assert d_final == 50.0
        assert updated is False

    def test_large_change_updated(self):
        """Perubahan >= delta_d_update (5%) diterapkan seketika."""
        # Tepat 5%
        d_final, updated = apply_hysteresis(
            d_candidate=55.0,
            d_prev=50.0,
            is_off_condition=False,
            delta_d_update=5.0
        )
        assert d_final == 55.0
        assert updated is True

        # Lebih besar dari 5%
        d_final, updated = apply_hysteresis(
            d_candidate=42.0,
            d_prev=50.0,
            is_off_condition=False,
            delta_d_update=5.0
        )
        assert d_final == 42.0
        assert updated is True

    def test_immediate_turn_off_without_hysteresis(self):
        """Kondisi mati langsung menjadi 0% tanpa terhalang ambang histeresis."""
        # Walaupun perbedaannya kecil misal 32% ke 0%, harus langsung mati!
        d_final, updated = apply_hysteresis(
            d_candidate=0.0,
            d_prev=32.0,
            is_off_condition=True,
            delta_d_update=5.0
        )
        assert d_final == 0.0
        assert updated is True


class TestMockPWMDriverAndController:
    """Pengujian Mock Driver dan integrasi FanPWMController."""

    def test_mock_driver_commands(self):
        driver = MockPWMDriver()
        assert driver.get_duty_cycle() == 0.0

        driver.set_duty_cycle(45.5)
        assert driver.get_duty_cycle() == 45.5
        assert len(driver.history) == 1
        assert driver.history[0]["pwm_percent"] == 45.5

        # Uji proteksi clipping di driver
        driver.set_duty_cycle(120.0)
        assert driver.get_duty_cycle() == 100.0

        driver.set_duty_cycle(-10.0)
        assert driver.get_duty_cycle() == 0.0

        driver.cleanup()
        assert driver.get_duty_cycle() == 0.0
        assert len(driver.history) == 0

    def test_fan_controller_integrated_cycle(self):
        mock_driver = MockPWMDriver()
        controller = FanPWMController(driver=mock_driver)

        # Siklus 1: Dari kondisi awal (mati) ke aktif
        res1 = controller.compute_and_apply(u_zona=51.66, has_valid_data=True)
        # u_zona 51.66 -> ratio (51.66 - 15) / (88.33 - 15) = 0.50 -> PWM = 30 + 0.5 * 70 = 65%
        assert res1["candidate_pwm"] == pytest.approx(65.0, abs=0.1)
        assert res1["final_pwm"] == pytest.approx(65.0, abs=0.1)
        assert res1["fan_command_status"] == "Aktif"
        assert mock_driver.get_duty_cycle() == pytest.approx(65.0, abs=0.1)

        # Siklus 2: Fluktuasi kecil (u_zona sedikit turun) -> tertahan histeresis
        res2 = controller.compute_and_apply(u_zona=50.0, has_valid_data=True)
        assert res2["is_hysteresis_updated"] is False
        assert res2["final_pwm"] == res1["final_pwm"]

        # Siklus 3: Kondisi mati (u_zona <= 15) -> langsung 0%
        res3 = controller.compute_and_apply(u_zona=12.0, has_valid_data=True)
        assert res3["candidate_pwm"] == 0.0
        assert res3["final_pwm"] == 0.0
        assert res3["fan_command_status"] == "Mati"
        assert mock_driver.get_duty_cycle() == 0.0

        # Siklus 4: V(t) kosong (tidak ada data valid) -> PWM 0% dan status Kendali tidak tersedia
        res4 = controller.compute_and_apply(u_zona=None, has_valid_data=False)
        assert res4["final_pwm"] == 0.0
        assert res4["fan_command_status"] == "Kendali tidak tersedia"


if __name__ == "__main__":
    print("=== Menjalankan Unit Test Agregasi Zona & Pemetaan PWM ===")
    test_classes = [
        TestZoneAggregation,
        TestPWMCalculation,
        TestHysteresisLogic,
        TestMockPWMDriverAndController
    ]

    total_passed = 0
    total_tests = 0

    for cls in test_classes:
        instance = cls()
        methods = [m for m in dir(instance) if m.startswith("test_")]
        print(f"\n[Menjalankan {cls.__name__}]")
        for method_name in methods:
            test_method = getattr(instance, method_name)
            total_tests += 1
            try:
                test_method()
                print(f"  [PASS] {method_name}")
                total_passed += 1
            except Exception as e:
                print(f"  [FAIL] {method_name}: {e}")
                raise

    print(f"\n==========================================")
    print(f"Hasil: {total_passed}/{total_tests} Pengujian Berhasil Lolos 100%!")
    print(f"==========================================")
