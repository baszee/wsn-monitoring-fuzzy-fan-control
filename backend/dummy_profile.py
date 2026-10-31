"""Generator data sensor uji yang halus. Dipakai backfill_dummy.py dan feed_dummy.py
supaya riwayat dan data hidup menyambung tanpa lonjakan."""
import math
import random

# Karakter tiap node: selisih suhu, selisih RH, dasar debu, dan kejadian debu (jam, lebar jam, tegangan tambahan)
PROFILE = {
    "NODE-01": dict(dt=-0.8, drh=+2.0, dust0=0.25, bumps=[(11.0, 0.7, 0.5)]),
    "NODE-02": dict(dt=0.0, drh=0.0, dust0=0.35, bumps=[(10.5, 0.8, 0.9), (17.0, 0.7, 0.7)]),
    "NODE-03": dict(dt=+1.2, drh=-4.0, dust0=0.45, bumps=[(10.7, 0.8, 1.7), (15.8, 0.6, 2.2), (20.5, 0.8, 1.2)]),
}


class _Smooth:
    """Derau lambat (AR1) supaya kurva naik turun halus."""
    def __init__(self, sigma, rng, phi=0.985):
        self.x, self.sigma, self.phi, self.rng = 0.0, sigma, phi, rng

    def next(self, ratio):
        self.x = (self.phi ** ratio) * self.x + self.rng.gauss(0, self.sigma * math.sqrt(ratio))
        return self.x


class Generator:
    def __init__(self, seed: int = 7):
        self.rng = random.Random(seed)
        self.noise = {n: dict(t=_Smooth(0.05, self.rng), rh=_Smooth(0.25, self.rng), d=_Smooth(0.03, self.rng))
                      for n in PROFILE}

    def sample(self, node: str, hour: float, step_seconds: float = 60.0):
        """hour = jam lokal (0 sampai 24). Mengembalikan (suhu, RH, tegangan debu)."""
        p, ratio = PROFILE[node], step_seconds / 60.0
        phase = math.sin(2 * math.pi * (hour - 9.0) / 24.0)         # puncak suhu sekitar pukul 15.00
        temp = 27.6 + 3.6 * phase + p["dt"] + self.noise[node]["t"].next(ratio)
        rh = 50.0 - 6.0 * phase + p["drh"] + self.noise[node]["rh"].next(ratio)
        dust = p["dust0"] + 0.08 * phase
        for center, width, amp in p["bumps"]:
            d = min(abs(hour - center), 24 - abs(hour - center))
            dust += amp * math.exp(-(d * d) / (2 * width * width))
        dust += self.noise[node]["d"].next(ratio)
        return (round(min(max(temp, 16.0), 40.0), 2),
                round(min(max(rh, 20.0), 90.0), 1),
                round(min(max(dust, 0.08), 3.4), 3))
