"""
Unit Test untuk Modul Inferensi Fuzzy Mamdani Murni NumPy (tests/test_fuzzy.py).
Dapat dijalankan langsung dengan `python tests/test_fuzzy.py` atau melalui `pytest`.

Memverifikasi:
1. Normalisasi indeks debu (clipping, acuan C_0 dan C_H)
2. Fungsi keanggotaan trapmf dan trimf
3. Klasifikasi kondisi (Baik, Perlu Perhatian, Buruk)
4. Skenario inti: pemisahan skor kondisi vs kendali fan
5. Kasus batas & overlap partisi fuzzy
6. Rentang teoretis keluaran s_i dan u_i
7. Keterlacakan derajat keanggotaan dan daftar aturan aktif
"""

import sys
import os
import numpy as np

try:
    import pytest
except ImportError:
    # Fallback sederhana jika pytest belum terpasang di environment
    class MockPytest:
        @staticmethod
        def approx(expected, rel=None, abs_tol=1e-3, **kwargs):
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

from app.services.fuzzy import (
    normalize_dust,
    trimf,
    trapmf,
    classify_condition,
    evaluate_fuzzy,
    FuzzyMamdaniEngine
)
from app.settings import CENTROID_TEST_TOLERANCE, CENTROID_STEP


class TestDustNormalization:
    """Uji normalisasi nilai sensor debu ke indeks 0 - 1."""

    def test_dust_normal_range(self):
        # Titik tengah (0.05 + 3.50) / 2 = 1.775
        idx = normalize_dust(1.775, c_0=0.05, c_h=3.50)
        assert idx == pytest.approx(0.5, abs=0.001)

    def test_dust_clipping_below_c0(self):
        # Pembacaan di bawah C_0 harus di-clip ke 0.0
        assert normalize_dust(0.01, c_0=0.05, c_h=3.50) == 0.0
        assert normalize_dust(-0.5, c_0=0.05, c_h=3.50) == 0.0

    def test_dust_clipping_above_ch(self):
        # Pembacaan di atas C_H harus di-clip ke 1.0
        assert normalize_dust(3.55, c_0=0.05, c_h=3.50) == 1.0
        assert normalize_dust(5.00, c_0=0.05, c_h=3.50) == 1.0

    def test_dust_exact_boundary(self):
        assert normalize_dust(0.05, c_0=0.05, c_h=3.50) == 0.0
        assert normalize_dust(3.50, c_0=0.05, c_h=3.50) == 1.0

    def test_invalid_reference_raises_error(self):
        with pytest.raises(ValueError):
            normalize_dust(1.0, c_0=3.5, c_h=0.5)


class TestMembershipFunctions:
    """Uji fungsi keanggotaan trapesium dan segitiga."""

    def test_trimf_scalar(self):
        params = [10.0, 30.0, 50.0]
        assert trimf(5.0, params) == 0.0
        assert trimf(20.0, params) == 0.5
        assert trimf(30.0, params) == 1.0
        assert trimf(40.0, params) == 0.5
        assert trimf(60.0, params) == 0.0

    def test_trimf_vectorized(self):
        params = [10.0, 30.0, 50.0]
        x = np.array([5.0, 20.0, 30.0, 40.0, 60.0])
        res = trimf(x, params)
        assert np.allclose(res, [0.0, 0.5, 1.0, 0.5, 0.0])

    def test_trapmf_left_shoulder(self):
        # trapmf(0, 0, 16, 18) untuk Suhu Rendah
        params = [0.0, 0.0, 16.0, 18.0]
        assert trapmf(-5.0, params) == 1.0
        assert trapmf(10.0, params) == 1.0
        assert trapmf(16.0, params) == 1.0
        assert trapmf(17.0, params) == 0.5
        assert trapmf(18.0, params) == 0.0
        assert trapmf(25.0, params) == 0.0

    def test_trapmf_right_shoulder(self):
        # trapmf(30, 32, 50, 50) untuk Suhu Tinggi
        params = [30.0, 32.0, 50.0, 50.0]
        assert trapmf(25.0, params) == 0.0
        assert trapmf(30.0, params) == 0.0
        assert trapmf(31.0, params) == 0.5
        assert trapmf(32.0, params) == 1.0
        assert trapmf(45.0, params) == 1.0
        assert trapmf(55.0, params) == 1.0

    def test_partition_of_unity_overlap(self):
        # Di rentang overlap [16, 18], mu_Rendah + mu_Normal harus bernilai 1.0
        p_rendah = [0.0, 0.0, 16.0, 18.0]
        p_normal = [16.0, 18.0, 30.0, 32.0]
        for t in np.linspace(16.0, 18.0, 11):
            total_mu = trapmf(t, p_rendah) + trapmf(t, p_normal)
            assert total_mu == pytest.approx(1.0, abs=0.0001)


class TestConditionClassification:
    """Uji pemetaan skor s_i ke kelas Baik, Perlu Perhatian, Buruk."""

    def test_classification_intervals(self):
        assert classify_condition(0.0) == "Baik"
        assert classify_condition(20.5) == "Baik"
        assert classify_condition(34.99) == "Baik"

        # Titik batas seri: 35.0 harus ke kelas yang lebih buruk (Perlu Perhatian)
        assert classify_condition(35.0) == "Perlu Perhatian"
        assert classify_condition(50.0) == "Perlu Perhatian"
        assert classify_condition(64.99) == "Perlu Perhatian"

        # Titik batas seri: 65.0 harus ke kelas yang lebih buruk (Buruk)
        assert classify_condition(65.0) == "Buruk"
        assert classify_condition(85.0) == "Buruk"
        assert classify_condition(100.0) == "Buruk"


class TestFuzzyInferenceScenarios:
    """Uji inferensi skenario inti penelitian dan kasus batas."""

    def test_scenario_cold_dry_clean(self):
        """
        Skenario Inti (Bukti Pemisahan 2 Keluaran):
        Suhu Rendah (10 °C) + RH Kering (20%) + Debu Rendah (0.05 V -> index 0.0).
        Skor Kondisi harus BURUK (karena terlalu dingin dan kering),
        TETAPI kendali fan harus MATI (menyalakan fan tidak akan membantu udara dingin/kering).
        """
        res = evaluate_fuzzy(temperature=10.0, humidity=20.0, dust_raw=0.05)
        
        outputs = res["outputs"]
        assert outputs["condition_class"] == "Buruk"
        # s_i berada di rentang tinggi (> 65)
        assert outputs["condition_score"] >= 65.0
        # u_i berada di sekitar centroid 'Mati' (~5.42)
        assert outputs["control_level"] <= 15.0

        # Verifikasi aturan yang aktif adalah Rule 1
        active_ids = [r["id"] for r in res["active_rules"]]
        assert 1 in active_ids

    def test_scenario_ideal_comfortable(self):
        """
        Kondisi Ideal: Suhu 24 °C, RH 50%, Debu 0.1 V (Indeks Rendah).
        Skor kondisi harus BAIK, kendali fan MATI.
        """
        res = evaluate_fuzzy(temperature=24.0, humidity=50.0, dust_raw=0.10)
        outputs = res["outputs"]

        assert outputs["condition_class"] == "Baik"
        assert outputs["condition_score"] < 35.0
        assert outputs["control_level"] <= 15.0

        active_ids = [r["id"] for r in res["active_rules"]]
        assert 5 in active_ids  # Rule 5: Rendah x Normal x Normal -> Baik / Mati

    def test_scenario_heavy_dust_triggers_high_fan(self):
        """
        Kondisi Debu Tinggi: Debu 3.5 V (Indeks 1.0).
        Semua kombinasi pada Debu Tinggi menghasilkan Buruk / Tinggi.
        """
        res = evaluate_fuzzy(temperature=26.0, humidity=55.0, dust_raw=3.50)
        outputs = res["outputs"]

        assert outputs["condition_class"] == "Buruk"
        assert outputs["condition_score"] >= 65.0
        # u_i berada di sekitar centroid 'Tinggi' (~88.33) dengan toleransi
        assert abs(outputs["control_level"] - 88.33) <= CENTROID_TEST_TOLERANCE

    def test_theoretical_bounds(self):
        """
        Verifikasi rentang teoretis keluaran Mamdani dengan centroid:
        s_i berada di [15.56, 84.44] (+/- toleransi diskretisasi)
        u_i berada di [5.42, 88.33] (+/- toleransi diskretisasi)
        """
        # Minimum mungkin untuk s_i dan u_i
        res_min = evaluate_fuzzy(temperature=24.0, humidity=50.0, dust_index=0.0)
        assert res_min["outputs"]["condition_score"] >= 15.0
        assert res_min["outputs"]["control_level"] >= 5.0

        # Maksimum mungkin untuk s_i dan u_i
        res_max = evaluate_fuzzy(temperature=40.0, humidity=20.0, dust_index=1.0)
        assert res_max["outputs"]["condition_score"] <= 85.0
        assert abs(res_max["outputs"]["control_level"] - 88.33) <= CENTROID_TEST_TOLERANCE

    def test_transparency_and_curves(self):
        """Uji kelengkapan data transparansi untuk dashboard (FR-12 & FR-13)."""
        res = evaluate_fuzzy(
            temperature=28.0,
            humidity=62.0,
            dust_raw=0.8,
            include_curves=True
        )

        assert "inputs" in res
        assert "memberships" in res
        assert "active_rules" in res
        assert "all_rules" in res
        assert "curves" in res

        # Periksa kebenaran memberships
        assert 0.0 <= res["memberships"]["temperature"]["Normal"] <= 1.0
        assert 0.0 <= res["memberships"]["humidity"]["Lembap"] <= 1.0

        # Periksa bahwa semua active_rules memiliki alpha > 0
        for rule in res["active_rules"]:
            assert rule["alpha"] > 0.0

        # Periksa kurva agregasi semesta (sesuai resolusi CENTROID_STEP)
        expected_points = int(round(100.0 / CENTROID_STEP)) + 1
        assert len(res["curves"]["universe"]) == expected_points
        assert len(res["curves"]["condition_score_aggregated"]) == expected_points
        assert len(res["curves"]["control_level_aggregated"]) == expected_points

    def test_determinism(self):
        """Dua kali evaluasi dengan input yang sama harus menghasilkan output identik."""
        res1 = evaluate_fuzzy(temperature=29.3, humidity=48.2, dust_raw=1.25)
        res2 = evaluate_fuzzy(temperature=29.3, humidity=48.2, dust_raw=1.25)

        assert res1["outputs"]["condition_score"] == res2["outputs"]["condition_score"]
        assert res1["outputs"]["control_level"] == res2["outputs"]["control_level"]
        assert res1["outputs"]["condition_class"] == res2["outputs"]["condition_class"]


if __name__ == "__main__":
    print("=== Menjalankan Unit Test Fuzzy Mamdani ===")
    test_classes = [
        TestDustNormalization,
        TestMembershipFunctions,
        TestConditionClassification,
        TestFuzzyInferenceScenarios
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
