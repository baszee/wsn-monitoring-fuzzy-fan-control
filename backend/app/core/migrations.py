"""Jalankan migrasi Alembic untuk tabel milik WSNova saja."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.core.database import APP_SCHEMA, engine


ROOT_DIR = Path(__file__).resolve().parents[3]
APP_TABLES = {
    "zone_nodes",
    "control_config",
    "mock_receiver_valid_data",
    "fuzzy_results",
    "zone_controls",
}


def alembic_config() -> Config:
    cfg = Config(str(ROOT_DIR / "alembic.ini"))
    cfg.set_main_option(
        "script_location", (ROOT_DIR / "backend" / "migrations").as_posix()
    )
    return cfg


def _ensure_app_schema() -> None:
    if APP_SCHEMA and engine.dialect.name == "postgresql":
        # APP_SCHEMA sudah divalidasi ketat oleh app.core.config.
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{APP_SCHEMA}"'))


def _existing_tables() -> set[str]:
    return set(inspect(engine).get_table_names(schema=APP_SCHEMA))


def upgrade_database(revision: str = "head") -> None:
    """Upgrade schema aplikasi, termasuk baseline aman untuk database pra-Alembic."""
    _ensure_app_schema()
    cfg = alembic_config()
    tables = _existing_tables()

    # Database yang sudah dipakai sebelum Alembic tidak memiliki alembic_version.
    # Tandai revisi sesuai bentuk aktual, lalu lanjutkan migrasi normal.
    if "alembic_version" not in tables:
        existing_app_tables = tables & APP_TABLES
        if existing_app_tables:
            if "fuzzy_results" not in existing_app_tables:
                raise RuntimeError(
                    "Database WSNova lama tidak lengkap; fuzzy_results tidak ditemukan. "
                    "Gunakan database baru atau pulihkan schema sebelum migrasi."
                )
            columns = {
                column["name"]
                for column in inspect(engine).get_columns(
                    "fuzzy_results", schema=APP_SCHEMA
                )
            }
            baseline = "0002_source_identity" if "source_name" in columns else "0001_initial"
            command.stamp(cfg, baseline)

    command.upgrade(cfg, revision)
