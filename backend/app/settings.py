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


# Sumber sensor:
#   mock          -> tabel tiruan mock_receiver_valid_data (pengembangan/demo)
#   paket_valid   -> tabel paket_valid milik penerima M2 (schema.sql terbaru)
#   node_readings -> tabel lama penerima M2 (dipertahankan untuk kompatibilitas)
# Nilai lain ditolak saat start agar aplikasi tidak diam-diam memakai data tiruan.
SENSOR_SOURCES = ("mock", "paket_valid", "node_readings")
SENSOR_SOURCE = os.getenv("SENSOR_SOURCE", "mock").strip().lower()
if SENSOR_SOURCE not in SENSOR_SOURCES:
    raise ValueError(
        f"SENSOR_SOURCE={SENSOR_SOURCE!r} tidak dikenal; pilih salah satu dari "
        f"{', '.join(SENSOR_SOURCES)}."
    )

# Filter mode sesi_uji untuk sumber paket_valid, dipisah koma (mis. "sensor").
# Kosong = semua sesi, sesuai schema penerima yang menyebut paket_valid sebagai
# sumber data dashboard. Isi "sensor" bila baris sesi uji jarak/BER tidak boleh
# memengaruhi fuzzy dan kendali fan.
PAKET_VALID_SESSION_MODES = os.getenv("PAKET_VALID_SESSION_MODES", "").strip().lower()
_paket_valid_modes = {
    mode.strip() for mode in PAKET_VALID_SESSION_MODES.split(",") if mode.strip()
}
_invalid_paket_valid_modes = _paket_valid_modes - {"sensor", "uji"}
if _invalid_paket_valid_modes:
    raise ValueError(
        "PAKET_VALID_SESSION_MODES berisi nilai tidak dikenal: "
        f"{', '.join(sorted(_invalid_paket_valid_modes))}; gunakan sensor dan/atau uji."
    )

# Kesegaran data (detik). Node M2 mengirim sekitar tiap 10 detik, sehingga 30
# detik memberi ruang untuk jitter jaringan dan penulisan database.
FRESHNESS_SECONDS = _int("FRESHNESS_SECONDS", 30)

# Node sensor yang dipasang pada ZONA-1, dipisah koma. Prototipe saat ini memakai
# dua node; tambahkan "NODE-03" bila node ketiga benar-benar dipasang. Bootstrap
# menonaktifkan node lain (riwayatnya tetap disimpan, tidak dihapus).
def _node_ids(raw: str) -> tuple:
    ids = []
    for part in raw.split(","):
        part = part.strip().upper()
        if not part:
            continue
        if part.isdigit():
            part = f"NODE-{int(part):02d}"
        if part not in ids:
            ids.append(part)
    if not ids:
        raise ValueError("ZONE_NODE_IDS tidak boleh kosong; contoh: NODE-01,NODE-02")
    return tuple(ids)


ZONE_NODE_IDS = _node_ids(os.getenv("ZONE_NODE_IDS", "NODE-01,NODE-02"))

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

# Hanya satu instance WSNova yang boleh memproses fuzzy dan mengendalikan fan.
# Instance dashboard/read-only milik anggota tim harus mengisi false.
WORKER_ENABLED = _bool("WORKER_ENABLED", True)

# Driver keluaran fan. ``mock`` aman untuk Vercel/PC tanpa perangkat;
# ``arduino`` mengirim perintah ke bridge PWM melalui USB serial. Driver
# Orange Pi disediakan sebagai pilihan konfigurasi sejak awal, tetapi akan
# menolak start sampai implementasi GPIO untuk board aktual tersedia.
PWM_DRIVERS = ("mock", "arduino", "orangepi")
PWM_DRIVER = os.getenv("PWM_DRIVER", "mock").strip().lower()
if PWM_DRIVER not in PWM_DRIVERS:
    raise ValueError(
        f"PWM_DRIVER={PWM_DRIVER!r} tidak dikenal; pilih salah satu dari "
        f"{', '.join(PWM_DRIVERS)}."
    )

PWM_SERIAL_PORT = os.getenv("PWM_SERIAL_PORT", "").strip()
PWM_SERIAL_BAUD = _int("PWM_SERIAL_BAUD", 115200)
PWM_SERIAL_TIMEOUT_SECONDS = _float("PWM_SERIAL_TIMEOUT_SECONDS", 2.0)
PWM_SERIAL_STARTUP_SECONDS = _float("PWM_SERIAL_STARTUP_SECONDS", 2.0)
PWM_FREQUENCY_HZ = _int("PWM_FREQUENCY_HZ", 25000)
PWM_INVERTED = _bool("PWM_INVERTED", True)

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
