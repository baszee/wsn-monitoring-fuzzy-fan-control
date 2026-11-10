import os
import re
from pathlib import Path
from pydantic import BaseModel

def load_local_env():
    """Membaca file .env sederhana jika tersedia tanpa dependensi tambahan."""
    env_paths = [
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent.parent / ".env",
    ]
    for env_path in env_paths:
        if env_path.is_file():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("\"'")
                        if key not in os.environ:
                            os.environ[key] = val
            break

load_local_env()

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_SQLITE_PATH = (ROOT_DIR / "wsn.db").as_posix()


def normalize_database_url(url: str) -> str:
    """Gunakan driver psycopg 3 untuk URL PostgreSQL generik dari penyedia hosting."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

_SCHEMA_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def schema_name(env_name: str) -> str:
    """Baca nama schema PostgreSQL dari environment; kosong berarti search_path bawaan."""
    value = os.getenv(env_name, "").strip()
    if value and not _SCHEMA_NAME.fullmatch(value):
        raise ValueError(
            f"{env_name}={value!r} tidak valid: gunakan huruf kecil, angka, dan garis bawah."
        )
    return value


class Settings(BaseModel):
    PROJECT_NAME: str = "WSN Fuzzy Fan Control & Monitoring"
    PROJECT_VERSION: str = "0.1.0"
    
    # URL Database (Default: SQLite absolut di root project, atau PostgreSQL jika dispesifikasikan)
    DATABASE_URL: str = normalize_database_url(
        os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")
    )

    # Schema PostgreSQL untuk tabel milik WSNova (zone_nodes, control_config,
    # fuzzy_results, zone_controls). Kosong = search_path bawaan (perilaku lama).
    # Contoh: APP_DB_SCHEMA=wsnova agar tabel WSNova terpisah dari tabel penerima.
    APP_DB_SCHEMA: str = schema_name("APP_DB_SCHEMA")

    # Schema tabel milik penerima (sesi_uji, paket_valid, node_readings). Kosong =
    # search_path bawaan, atau "public" bila APP_DB_SCHEMA diisi.
    SOURCE_DB_SCHEMA: str = schema_name("SOURCE_DB_SCHEMA")

    # Akun admin (satu akun). Kata sandi disimpan sebagai hash, dibuat dengan make_admin_hash.py.
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "")
    ADMIN_PASSWORD_HASH: str = os.getenv("ADMIN_PASSWORD_HASH", "")
    # Isi true bila dashboard diakses lewat HTTPS. Di localhost (HTTP) harus false.
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").strip().lower() in ("1", "true", "yes")

settings = Settings()
