"""
Layanan Inferensi Fuzzy Mamdani Murni NumPy (Tanpa scikit-fuzzy).

Memproses 3 masukan sensor (Suhu, Kelembapan Relatif / RH, Indeks Debu)
menjadi dua keluaran terpisah:
1. Skor Kondisi Lingkungan (s_i, semesta 0 - 100) -> Kelas Kondisi (k_i)
2. Tingkat Kendali Fan (u_i, semesta 0 - 100)

Fitur:
- Normalisasi Indeks Debu dengan batasan clip [0, 1]
- Fungsi keanggotaan trapesium (trapmf) dan segitiga (trimf)
- 27 Aturan Mamdani Min-Max
- Defuzzifikasi Centroid Diskret (langkah 0.1)
- Keterlacakan penuh: derajat keanggotaan masukan, alpha_r per aturan, dan kurva agregasi
"""

from typing import Dict, List, Any, Optional, Tuple, Union
import numpy as np


def normalize_dust(raw_val: float, c_0: float = 0.05, c_h: float = 3.50) -> float:
    """
    Normalisasi nilai pembacaan sensor debu ke indeks relatif 0 - 1.
    Formula: I_d,i = clip((C_i - C_0) / (C_H - C_0), 0, 1)
    """
    if c_h <= c_0:
        raise ValueError("c_h (acuan tinggi) harus lebih besar dari c_0 (acuan rendah).")
    normalized = (float(raw_val) - float(c_0)) / (float(c_h) - float(c_0))
    return float(np.clip(normalized, 0.0, 1.0))


def trimf(x: Union[float, np.ndarray], params: List[float]) -> Union[float, np.ndarray]:
    """
    Fungsi keanggotaan segitiga (Triangular Membership Function).
    params: [a, b, c] dengan a <= b <= c
    """
    a, b, c = float(params[0]), float(params[1]), float(params[2])
    x_arr = np.asarray(x, dtype=np.float64)
    y = np.zeros_like(x_arr)

    # Lereng kiri: a < x < b
    if b > a:
        left_mask = (x_arr > a) & (x_arr < b)
        y[left_mask] = (x_arr[left_mask] - a) / (b - a)
    elif a == b:
        y[x_arr <= b] = 1.0

    # Puncak: x == b
    y[x_arr == b] = 1.0

    # Lereng kanan: b < x < c
    if c > b:
        right_mask = (x_arr > b) & (x_arr < c)
        y[right_mask] = (c - x_arr[right_mask]) / (c - b)
    elif b == c:
        y[x_arr >= b] = 1.0

    return float(y) if np.ndim(x) == 0 else y


def trapmf(x: Union[float, np.ndarray], params: List[float]) -> Union[float, np.ndarray]:
    """
    Fungsi keanggotaan trapesium (Trapezoidal Membership Function).
    params: [a, b, c, d] dengan a <= b <= c <= d
    """
    a, b, c, d = float(params[0]), float(params[1]), float(params[2]), float(params[3])
    x_arr = np.asarray(x, dtype=np.float64)
    y = np.zeros_like(x_arr)

    # Lereng / bahu kiri
    if b > a:
        left_mask = (x_arr > a) & (x_arr < b)
        y[left_mask] = (x_arr[left_mask] - a) / (b - a)
    elif a == b:
        y[x_arr <= b] = 1.0

    # Puncak datar (plateau): b <= x <= c
    plateau_mask = (x_arr >= b) & (x_arr <= c)
    y[plateau_mask] = 1.0

    # Lereng / bahu kanan
    if d > c:
        right_mask = (x_arr > c) & (x_arr < d)
        y[right_mask] = (d - x_arr[right_mask]) / (d - c)
    elif c == d:
        y[x_arr >= c] = 1.0

    return float(y) if np.ndim(x) == 0 else y


def evaluate_mf(x: Union[float, np.ndarray], mf_spec: Dict[str, Any]) -> Union[float, np.ndarray]:
    """Mengevaluasi keanggotaan berdasarkan spesifikasi {'type': 'trapmf'|'trimf', 'params': [...]}."""
    mf_type = mf_spec.get("type")
    params = mf_spec.get("params", [])
    if mf_type == "trapmf":
        return trapmf(x, params)
    elif mf_type == "trimf":
        return trimf(x, params)
    else:
        raise ValueError(f"Tipe fungsi keanggotaan tidak dikenali: {mf_type}")


def classify_condition(score: float) -> str:
    """
    Menentukan kelas kondisi lingkungan berdasarkan skor s_i:
    - 0 <= s < 35  -> Baik
    - 35 <= s < 65 -> Perlu Perhatian
    - 65 <= s <= 100 -> Buruk
    (Seri di titik batas 35 & 65 diarahkan ke kelas yang lebih buruk).
    """
    if score < 35.0:
        return "Baik"
    elif score < 65.0:
        return "Perlu Perhatian"
    else:
        return "Buruk"


# Parameter default fungsi keanggotaan sesuai PRD Subbab 9.2
DEFAULT_MEMBERSHIP_PARAMS = {
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

# Basis 27 Aturan Mamdani sesuai PRD Subbab 9.3
DEFAULT_RULE_BASE = [
    # Debu Rendah
    {"id": 1, "dust": "Rendah", "rh": "Kering", "temp": "Rendah", "condition_class": "Buruk", "control_level": "Mati"},
    {"id": 2, "dust": "Rendah", "rh": "Kering", "temp": "Normal", "condition_class": "Perlu Perhatian", "control_level": "Mati"},
    {"id": 3, "dust": "Rendah", "rh": "Kering", "temp": "Tinggi", "condition_class": "Buruk", "control_level": "Rendah"},
    {"id": 4, "dust": "Rendah", "rh": "Normal", "temp": "Rendah", "condition_class": "Perlu Perhatian", "control_level": "Mati"},
    {"id": 5, "dust": "Rendah", "rh": "Normal", "temp": "Normal", "condition_class": "Baik", "control_level": "Mati"},
    {"id": 6, "dust": "Rendah", "rh": "Normal", "temp": "Tinggi", "condition_class": "Perlu Perhatian", "control_level": "Rendah"},
    {"id": 7, "dust": "Rendah", "rh": "Lembap", "temp": "Rendah", "condition_class": "Buruk", "control_level": "Rendah"},
    {"id": 8, "dust": "Rendah", "rh": "Lembap", "temp": "Normal", "condition_class": "Perlu Perhatian", "control_level": "Rendah"},
    {"id": 9, "dust": "Rendah", "rh": "Lembap", "temp": "Tinggi", "condition_class": "Buruk", "control_level": "Sedang"},

    # Debu Sedang
    {"id": 10, "dust": "Sedang", "rh": "Kering", "temp": "Rendah", "condition_class": "Buruk", "control_level": "Sedang"},
    {"id": 11, "dust": "Sedang", "rh": "Kering", "temp": "Normal", "condition_class": "Perlu Perhatian", "control_level": "Sedang"},
    {"id": 12, "dust": "Sedang", "rh": "Kering", "temp": "Tinggi", "condition_class": "Buruk", "control_level": "Tinggi"},
    {"id": 13, "dust": "Sedang", "rh": "Normal", "temp": "Rendah", "condition_class": "Perlu Perhatian", "control_level": "Sedang"},
    {"id": 14, "dust": "Sedang", "rh": "Normal", "temp": "Normal", "condition_class": "Perlu Perhatian", "control_level": "Sedang"},
    {"id": 15, "dust": "Sedang", "rh": "Normal", "temp": "Tinggi", "condition_class": "Perlu Perhatian", "control_level": "Tinggi"},
    {"id": 16, "dust": "Sedang", "rh": "Lembap", "temp": "Rendah", "condition_class": "Buruk", "control_level": "Tinggi"},
    {"id": 17, "dust": "Sedang", "rh": "Lembap", "temp": "Normal", "condition_class": "Perlu Perhatian", "control_level": "Tinggi"},
    {"id": 18, "dust": "Sedang", "rh": "Lembap", "temp": "Tinggi", "condition_class": "Buruk", "control_level": "Tinggi"},

    # Debu Tinggi (Semua kombinasi menghasilkan Buruk / Tinggi)
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


class FuzzyMamdaniEngine:
    """
    Mesin Inferensi Fuzzy Mamdani berkecepatan tinggi dengan pure NumPy.
    Mendukung konfigurasi parameter dinamis dan perhitungan deterministik.
    """

    def __init__(
        self,
        membership_params: Optional[Dict[str, Any]] = None,
        rule_base: Optional[List[Dict[str, Any]]] = None,
        universe_step: float = 0.1
    ):
        self.membership_params = membership_params or DEFAULT_MEMBERSHIP_PARAMS
        self.rule_base = rule_base or DEFAULT_RULE_BASE
        self.step = universe_step

        # Diskretisasi semesta output 0 - 100 dengan langkah 0.1 (total 1001 titik)
        # Gunakan np.linspace untuk presisi titik floating point yang tepat
        num_points = int(round(100.0 / universe_step)) + 1
        self.universe = np.linspace(0.0, 100.0, num_points)

        # Prekomputasi kurva fungsi keanggotaan output pada semesta diskret
        self._precompute_output_mfs()

    def _precompute_output_mfs(self):
        """Pre-komputasi MF output agar proses inferensi per siklus sangat cepat."""
        self.score_mfs = {}
        for name, spec in self.membership_params["condition_score"].items():
            self.score_mfs[name] = evaluate_mf(self.universe, spec)

        self.control_mfs = {}
        for name, spec in self.membership_params["control_level"].items():
            self.control_mfs[name] = evaluate_mf(self.universe, spec)

    def evaluate(
        self,
        temperature: float,
        humidity: float,
        dust_raw: Optional[float] = None,
        dust_index: Optional[float] = None,
        dust_low_ref: float = 0.05,
        dust_high_ref: float = 3.50,
        include_curves: bool = False
    ) -> Dict[str, Any]:
        """
        Menjalankan satu siklus inferensi Fuzzy Mamdani lengkap.
        
        Parameter:
            temperature: Suhu (°C), semesta 0 - 50
            humidity: Kelembapan Relatif / RH (%), semesta 0 - 100
            dust_raw: Tegangan/nilai mentah sensor debu (akan dinormalisasi jika diberikan)
            dust_index: Indeks debu (0 - 1) jika sudah dinormalisasi
            dust_low_ref: Acuan C_0 untuk normalisasi debu
            dust_high_ref: Acuan C_H untuk normalisasi debu
            include_curves: Jika True, menyertakan array kurva agregasi output (untuk visualisasi)
        
        Mengembalikan:
            Dictionary lengkap berisi skor s_i, kelas k_i, kendali u_i,
            derajat keanggotaan masukan, dan daftar aturan aktif.
        """
        # 1. Normalisasi Indeks Debu jika masukan berupa dust_raw
        if dust_index is None:
            if dust_raw is None:
                raise ValueError("Harus menyediakan dust_raw atau dust_index.")
            d_idx = normalize_dust(dust_raw, c_0=dust_low_ref, c_h=dust_high_ref)
        else:
            d_idx = float(np.clip(dust_index, 0.0, 1.0))

        temp_val = float(temperature)
        rh_val = float(humidity)

        # 2. Fuzzifikasi: Hitung derajat keanggotaan masukan (μ)
        mu_temp = {
            name: float(evaluate_mf(temp_val, spec))
            for name, spec in self.membership_params["temp"].items()
        }
        mu_rh = {
            name: float(evaluate_mf(rh_val, spec))
            for name, spec in self.membership_params["rh"].items()
        }
        mu_dust = {
            name: float(evaluate_mf(d_idx, spec))
            for name, spec in self.membership_params["dust"].items()
        }

        # 3. Evaluasi 27 Aturan & Implikasi Min
        # Inisialisasi kurva agregasi semesta dengan nol
        agg_score = np.zeros_like(self.universe)
        agg_control = np.zeros_like(self.universe)

        active_rules = []
        all_rules_evaluated = []

        for rule in self.rule_base:
            rule_id = rule["id"]
            d_label = rule["dust"]
            rh_label = rule["rh"]
            t_label = rule["temp"]
            score_label = rule["condition_class"]
            control_label = rule["control_level"]

            # Derajat aktivasi aturan: alpha_r = min(mu_temp, mu_rh, mu_dust)
            alpha_r = min(mu_temp[t_label], mu_rh[rh_label], mu_dust[d_label])

            rule_record = {
                "id": rule_id,
                "dust": d_label,
                "rh": rh_label,
                "temp": t_label,
                "condition_class": score_label,
                "control_level": control_label,
                "alpha": float(alpha_r)
            }
            all_rules_evaluated.append(rule_record)

            if alpha_r > 0.0:
                active_rules.append(rule_record)

                # Implikasi Min: potong kurva konsekuen dengan alpha_r
                # Agregasi Max: gabungkan antar aturan aktif
                clipped_score = np.minimum(alpha_r, self.score_mfs[score_label])
                agg_score = np.maximum(agg_score, clipped_score)

                clipped_control = np.minimum(alpha_r, self.control_mfs[control_label])
                agg_control = np.maximum(agg_control, clipped_control)

        # 4. Defuzzifikasi Centroid Diskret:
        # Centroid = sum(x * mu(x)) / sum(mu(x))
        sum_mu_score = float(np.sum(agg_score))
        if sum_mu_score > 0.0:
            s_i = float(np.sum(self.universe * agg_score) / sum_mu_score)
        else:
            s_i = 50.0  # Fallback netral jika tidak ada aturan yang terpicu

        sum_mu_control = float(np.sum(agg_control))
        if sum_mu_control > 0.0:
            u_i = float(np.sum(self.universe * agg_control) / sum_mu_control)
        else:
            u_i = 0.0   # Fallback aman: kipas dimatikan

        # 5. Penentuan Kelas Kondisi Lingkungan
        k_i = classify_condition(s_i)

        # Bentuk hasil keluaran lengkap untuk transparansi penuh
        result = {
            "inputs": {
                "temperature": round(temp_val, 2),
                "humidity": round(rh_val, 2),
                "dust_raw": round(dust_raw, 4) if dust_raw is not None else None,
                "dust_index": round(d_idx, 4),
            },
            "memberships": {
                "temperature": {k: round(v, 4) for k, v in mu_temp.items()},
                "humidity": {k: round(v, 4) for k, v in mu_rh.items()},
                "dust": {k: round(v, 4) for k, v in mu_dust.items()},
            },
            "active_rules": active_rules,
            "all_rules": all_rules_evaluated,
            "outputs": {
                "condition_score": round(s_i, 2),
                "condition_class": k_i,
                "control_level": round(u_i, 2),
            }
        }

        if include_curves:
            result["curves"] = {
                "universe": self.universe.tolist(),
                "condition_score_aggregated": agg_score.tolist(),
                "control_level_aggregated": agg_control.tolist(),
            }

        return result


# Instance global default untuk kemudahan akses
default_fuzzy_engine = FuzzyMamdaniEngine()

def evaluate_fuzzy(
    temperature: float,
    humidity: float,
    dust_raw: Optional[float] = None,
    dust_index: Optional[float] = None,
    dust_low_ref: float = 0.05,
    dust_high_ref: float = 3.50,
    include_curves: bool = False
) -> Dict[str, Any]:
    """Helper fungsi publik untuk evaluasi inferensi Fuzzy Mamdani."""
    return default_fuzzy_engine.evaluate(
        temperature=temperature,
        humidity=humidity,
        dust_raw=dust_raw,
        dust_index=dust_index,
        dust_low_ref=dust_low_ref,
        dust_high_ref=dust_high_ref,
        include_curves=include_curves
    )
