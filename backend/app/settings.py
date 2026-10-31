import os


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


# Kesegaran data (detik). Satu sumber kebenaran untuk dashboard dan worker.
FRESHNESS_SECONDS = _int("FRESHNESS_SECONDS", 10)

# Interval worker memeriksa rekaman baru (detik).
WORKER_INTERVAL_SECONDS = _int("WORKER_INTERVAL_SECONDS", 1)

# Resolusi centroid (satuan skala 0-100). Lebih kecil = lebih halus.
CENTROID_STEP = _float("CENTROID_STEP", 0.01)

# Toleransi pembanding pada tes terhadap nilai teoretis.
CENTROID_TEST_TOLERANCE = _float("CENTROID_TEST_TOLERANCE", 0.05)

# Pembulatan angka yang ditampilkan di antarmuka.
DISPLAY_DECIMALS = _int("DISPLAY_DECIMALS", 1)

# Asal yang diizinkan CORS. Diisi eksplisit, tanpa "*".
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:8000").split(",")
    if o.strip()
]
