from typing import Optional

import os

from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

IS_POSTGRES = settings.DATABASE_URL.startswith("postgresql")

# Schema tabel WSNova. Hanya berlaku di PostgreSQL; SQLite tidak mengenal schema.
APP_SCHEMA: Optional[str] = (settings.APP_DB_SCHEMA or None) if IS_POSTGRES else None

# Schema tabel penerima. Bila tabel WSNova dipindah ke schema sendiri, tabel
# penerima harus ditulis lengkap (default "public") agar tidak ikut diterjemahkan.
SOURCE_SCHEMA: Optional[str] = (
    (settings.SOURCE_DB_SCHEMA or ("public" if APP_SCHEMA else None)) if IS_POSTGRES else None
)

# Create database engine
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine_kwargs = {
    "echo": False,
    "connect_args": connect_args,
}
# Function serverless (Vercel) hidup sebentar dan bisa berjalan paralel; menahan
# pool koneksi di sana cepat menghabiskan kuota pooler Supabase.
SERVERLESS = os.getenv("SERVERLESS_MODE", "").strip().lower() in {"1", "true", "yes", "on"} or (
    bool(os.getenv("VERCEL")) and os.getenv("SERVERLESS_MODE", "").strip().lower() not in {"0", "false", "no", "off"}
)
if SERVERLESS and not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update({"poolclass": NullPool, "pool_pre_ping": False})
elif not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update({
        "pool_size": 3,
        "max_overflow": 2,
        "pool_recycle": 300,
        "pool_pre_ping": True,
    })
engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
if APP_SCHEMA:
    # Tabel tanpa schema eksplisit (seluruh tabel WSNova) diarahkan ke APP_SCHEMA,
    # baik saat create_all maupun saat query. Tabel penerima memakai SOURCE_SCHEMA
    # eksplisit sehingga tidak terpengaruh.
    engine = engine.execution_options(schema_translate_map={None: APP_SCHEMA})

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative Base
Base = declarative_base()

def get_db():
    """Dependency for obtaining database sessions in FastAPI routes or workers."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
