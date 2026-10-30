"""
Layanan Pemetaan Sinyal PWM Fan DC 12V dan Abstraksi Driver GPIO (backend/app/services/pwm.py).

Menangani:
1. Pemetaan tingkat kendali u_zona ke duty cycle kandidat D_baru:
   - Jika V(t) = kosong atau u_zona <= u_off (15.0) -> D_baru = 0.0% (Fan mati).
   - Jika u_zona > u_off -> D_min + clip((u_zona - u_off)/(u_max - u_off), 0, 1) * (100 - D_min).
2. Mekanisme histeresis delta_d_update (5.0%):
   - Jika kondisi mati (u_zona <= u_off atau V kosong): D langsung 0.0% tanpa histeresis.
   - Jika status sebelumnya mati (D_prev = 0.0%): D langsung D_baru tanpa penahanan histeresis.
   - Jika berputar (D_prev > 0): hanya ubah jika |D_baru - D_prev| >= delta_d_update, selain itu pertahankan D_prev.
3. Driver PWM (Mock untuk PC/Testing lokal, dan antarmuka untuk GPIO Orange Pi).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple, List
import numpy as np


def calculate_candidate_pwm(
    u_zona: Optional[float],
    u_off: float = 15.0,
    u_max: float = 88.33,
    d_min: float = 30.0
) -> float:
    """
    Menghitung persentase duty cycle PWM kandidat (D_baru) dari nilai u_zona.

    Parameter:
        u_zona: Tingkat kendali zona (None jika data tidak valid)
        u_off: Batas mati fan (default 15.0)
        u_max: Nilai maksimum teoretis kendali zona (default 88.33)
        d_min: Duty cycle minimum agar motor fan mulai berputar mengatasi inersia (default 30.0%)

    Mengembalikan:
        Duty cycle kandidat dalam rentang 0.0 - 100.0%
    """
    if u_zona is None or u_zona <= u_off:
        return 0.0

    if u_max <= u_off:
        raise ValueError("u_max harus lebih besar dari u_off.")

    # Normalisasi rasio linear [0, 1]
    ratio = (float(u_zona) - float(u_off)) / (float(u_max) - float(u_off))
    ratio_clipped = float(np.clip(ratio, 0.0, 1.0))

    # Pemetaan ke rentang [D_min, 100%]
    d_candidate = float(d_min) + ratio_clipped * (100.0 - float(d_min))
    return float(round(np.clip(d_candidate, 0.0, 100.0), 2))


def apply_hysteresis(
    d_candidate: float,
    d_prev: float,
    is_off_condition: bool = False,
    delta_d_update: float = 5.0
) -> Tuple[float, bool]:
    """
    Menerapkan logika histeresis pada duty cycle PWM.

    Aturan PRD Subbab 10:
    1. Keadaan mati (V = kosong atau u_zona <= u_off): langsung 0% tanpa histeresis.
    2. Jika D(t-1) = 0%: langsung terapkan D_baru (start seketika).
    3. Jika D(t-1) > 0% dan D_baru > 0%:
       - Jika |D_baru - D(t-1)| >= delta_d_update: terapkan D_baru.
       - Selain itu: pertahankan D(t-1).

    Mengembalikan:
        (d_final: float, is_updated: bool)
    """
    # 1. Kondisi mati langsung 0%
    if is_off_condition or d_candidate == 0.0:
        return (0.0, d_prev != 0.0)

    # 2. Transisi dari mati ke aktif (start fan)
    if d_prev == 0.0:
        return (d_candidate, True)

    # 3. Transisi saat fan sudah berputar
    diff = abs(d_candidate - d_prev)
    if diff >= float(delta_d_update):
        return (d_candidate, True)
    else:
        # Perubahan terlalu kecil (< delta_d_update), pertahankan nilai sebelumnya
        return (d_prev, False)


# -----------------------------------------------------------------------------
# ABSTRAKSI DRIVER HARDWARE / MOCK PWM
# -----------------------------------------------------------------------------

class BasePWMDriver(ABC):
    """Antarmuka abstrak driver PWM motor fan."""

    @abstractmethod
    def set_duty_cycle(self, percent: float) -> None:
        """Mengatur sinyal PWM keluaran (0.0 - 100.0%)."""
        pass

    @abstractmethod
    def get_duty_cycle(self) -> float:
        """Mengambil status sinyal perintah PWM saat ini."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Mematikan sinyal PWM (0.0%)."""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Membersihkan resource GPIO/PWM."""
        pass


class MockPWMDriver(BasePWMDriver):
    """
    Mock Driver PWM untuk lingkungan pengujian dan sistem lokal (tanpa hardware fisik).
    Mencatat seluruh riwayat perintah yang dikirim untuk verifikasi.
    """

    def __init__(self, initial_pwm: float = 0.0):
        self.current_pwm = float(np.clip(initial_pwm, 0.0, 100.0))
        self.history: List[Dict[str, Any]] = []

    def set_duty_cycle(self, percent: float) -> None:
        clipped_val = float(round(np.clip(percent, 0.0, 100.0), 2))
        self.current_pwm = clipped_val
        self.history.append({
            "command": "set_duty_cycle",
            "pwm_percent": clipped_val
        })

    def get_duty_cycle(self) -> float:
        return self.current_pwm

    def stop(self) -> None:
        self.set_duty_cycle(0.0)

    def cleanup(self) -> None:
        self.stop()
        self.history.clear()


class FanPWMController:
    """
    Pengendali PWM terintegrasi yang menyimpan state D_prev,
    menghitung kandidat PWM, menerapkan histeresis, dan mengirimkan sinyal ke driver.
    """

    def __init__(
        self,
        driver: Optional[BasePWMDriver] = None,
        u_off: float = 15.0,
        u_max: float = 88.33,
        d_min: float = 30.0,
        delta_d_update: float = 5.0
    ):
        self.driver = driver or MockPWMDriver(initial_pwm=0.0)
        self.u_off = u_off
        self.u_max = u_max
        self.d_min = d_min
        self.delta_d_update = delta_d_update
        self.d_prev = 0.0  # State awal saat aplikasi start = 0%

    def compute_and_apply(
        self,
        u_zona: Optional[float],
        has_valid_data: bool = True
    ) -> Dict[str, Any]:
        """
        Memproses satu siklus pemetaan u_zona -> PWM, menerapkan histeresis,
        dan menyetel driver PWM.
        """
        is_off = (not has_valid_data) or (u_zona is None) or (u_zona <= self.u_off)

        # 1. Hitung kandidat PWM
        d_candidate = calculate_candidate_pwm(
            u_zona=u_zona if not is_off else None,
            u_off=self.u_off,
            u_max=self.u_max,
            d_min=self.d_min
        )

        # 2. Terapkan histeresis
        previous_pwm = self.d_prev          # simpan nilai lama SEBELUM diperbarui
        d_final, is_updated = apply_hysteresis(
            d_candidate=d_candidate,
            d_prev=previous_pwm,
            is_off_condition=is_off,
            delta_d_update=self.delta_d_update
        )

        # 3. Update driver fisik / mock
        self.driver.set_duty_cycle(d_final)
        self.d_prev = d_final

        # 4. Tentukan status perintah fan
        if not has_valid_data:
            fan_status = "Kendali tidak tersedia"
        elif d_final > 0.0:
            fan_status = "Aktif"
        else:
            fan_status = "Mati"

        return {
            "u_zona": u_zona,
            "candidate_pwm": d_candidate,
            "final_pwm": d_final,
            "previous_pwm": previous_pwm,
            "is_hysteresis_updated": is_updated,
            "fan_command_status": fan_status
        }
