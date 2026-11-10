"""Migrasi WSNova harus bekerja untuk database kosong dan database pra-Alembic."""

import os
from pathlib import Path
import sqlite3
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
MIGRATE = ROOT / "backend" / "migrate_db.py"


def _run_migration(db_path: Path, revision: str = "head") -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
        "SENSOR_SOURCE": "mock",
        "APP_DB_SCHEMA": "",
        "SOURCE_DB_SCHEMA": "",
    }
    return subprocess.run(
        [sys.executable, str(MIGRATE), "--revision", revision],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def _columns(db_path: Path, table: str) -> set[str]:
    with sqlite3.connect(db_path) as db:
        return {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}


def test_fresh_database_upgrades_to_head(tmp_path):
    db_path = tmp_path / "fresh.db"
    result = _run_migration(db_path)
    assert result.returncode == 0, result.stderr
    assert "source_name" in _columns(db_path, "fuzzy_results")
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0003_worker_heartbeat"
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"zone_nodes", "control_config", "fuzzy_results", "zone_controls"} <= tables
    assert "paket_valid" not in tables


def test_legacy_revision_backfills_source_name(tmp_path):
    db_path = tmp_path / "legacy.db"
    first = _run_migration(db_path, "0001_initial")
    assert first.returncode == 0, first.stderr

    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO control_config VALUES "
            "('v1', '{}', '[]', 0.05, 3.5, 15, 88.33, 30, 5, 1, CURRENT_TIMESTAMP)"
        )
        db.execute("INSERT INTO zone_nodes(zone_id,node_id,is_active) VALUES ('ZONA-1','NODE-01',1)")
        db.execute(
            "INSERT INTO fuzzy_results "
            "(zone_node_id,config_version,processing_cycle_id,source_record_id,source_timestamp,"
            "dust_index,condition_score,condition_class,control_level) VALUES "
            "(1,'v1','OLD-1',7,CURRENT_TIMESTAMP,0.2,20,'Baik',10)"
        )
        db.commit()

    second = _run_migration(db_path)
    assert second.returncode == 0, second.stderr
    assert "source_name" in _columns(db_path, "fuzzy_results")
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT source_name FROM fuzzy_results").fetchone()[0] == "legacy"
        unique_indexes = [
            row[1] for row in db.execute('PRAGMA index_list("fuzzy_results")') if row[2]
        ]
        indexed_columns = [
            [item[2] for item in db.execute(f'PRAGMA index_info("{name}")')]
            for name in unique_indexes
        ]
    assert ["source_name", "zone_node_id", "source_record_id", "config_version"] in indexed_columns
