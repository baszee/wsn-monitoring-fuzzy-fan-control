"""CLI migrasi database WSNova tanpa menyentuh tabel receiver."""

import argparse
from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.migrations import upgrade_database  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrasi tabel aplikasi WSNova")
    parser.add_argument(
        "--revision", default="head", help="Target revisi Alembic (default: head)"
    )
    args = parser.parse_args()
    upgrade_database(args.revision)
    print(f"Migrasi WSNova selesai pada revisi {args.revision}.")


if __name__ == "__main__":
    main()
