"""Lingkungan Alembic yang memakai konfigurasi database WSNova."""

from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import text
from sqlalchemy.engine import Connection


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.core.database import APP_SCHEMA, Base, engine  # noqa: E402
import app.models  # noqa: E402,F401  (daftarkan seluruh tabel pada Base.metadata)


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _configure(connection: Connection) -> None:
    if APP_SCHEMA and connection.dialect.name == "postgresql":
        connection.execute(text(f'SET search_path TO "{APP_SCHEMA}", public'))
        connection.commit()

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=connection.dialect.name == "sqlite",
        version_table_schema=APP_SCHEMA,
        include_schemas=bool(APP_SCHEMA),
    )


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=APP_SCHEMA,
        render_as_batch=settings.DATABASE_URL.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        _configure(connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
