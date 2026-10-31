import os
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

class Settings(BaseModel):
    PROJECT_NAME: str = "WSN Fuzzy Fan Control & Monitoring"
    PROJECT_VERSION: str = "0.1.0"
    
    # URL Database (Default: SQLite absolut di root project, atau PostgreSQL jika dispesifikasikan)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        f"sqlite:///{DEFAULT_SQLITE_PATH}"
    )

    # Akun admin (satu akun). Kata sandi disimpan sebagai hash, dibuat dengan make_admin_hash.py.
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "")
    ADMIN_PASSWORD_HASH: str = os.getenv("ADMIN_PASSWORD_HASH", "")
    # Isi true bila dashboard diakses lewat HTTPS. Di localhost (HTTP) harus false.
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").strip().lower() in ("1", "true", "yes")

settings = Settings()
