import os

from app.core import config as _env  # noqa: F401  (memuat berkas .env lebih dulu)


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


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


# Sumber sensor: mock (pengembangan sekarang) atau node_readings (tabel M2).
SENSOR_SOURCE = os.getenv("SENSOR_SOURCE", "mock").strip().lower()
if SENSOR_SOURCE not in {"mock", "node_readings"}:
    SENSOR_SOURCE = "mock"

# Kesegaran data (detik). Node M2 mengirim sekitar tiap 10 detik, sehingga 30
# detik memberi ruang untuk jitter jaringan dan penulisan database.
FRESHNESS_SECONDS = _int("FRESHNESS_SECONDS", 30)

# Interval worker memeriksa rekaman baru (detik).
WORKER_INTERVAL_SECONDS = _int("WORKER_INTERVAL_SECONDS", 1)

# Generator data tiruan opsional untuk demo daring satu layanan.
DEMO_MODE = _bool("DEMO_MODE", False)
DEMO_FEED_INTERVAL_SECONDS = _float("DEMO_FEED_INTERVAL_SECONDS", 3.0)
# Satu siklus kondisi demo (normal -> meningkat -> tinggi -> pulih).
# Nilai bawaan 10 menit membuat perubahan kendali terlihat saat demonstrasi
# tanpa mengubah perilaku ketika aplikasi memakai data penerima yang nyata.
DEMO_CYCLE_SECONDS = _float("DEMO_CYCLE_SECONDS", 600.0)

# Vercel dan platform function-as-a-service tidak menjamin task latar belakang
# tetap berjalan setelah respons selesai. Pada mode ini satu siklus dipicu oleh
# request dashboard, sedangkan deployment biasa/Orange Pi tetap memakai worker.
SERVERLESS_MODE = _bool("SERVERLESS_MODE", bool(os.getenv("VERCEL")))

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
