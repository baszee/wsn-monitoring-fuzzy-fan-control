"""Daftar node zona mengikuti ZONE_NODE_IDS (bawaan dua node)."""

import os
from pathlib import Path
import sqlite3
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "backend" / "bootstrap_db.py"


def _bootstrap(db_path: Path, node_ids=None) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
        "SENSOR_SOURCE": "mock",
        "APP_DB_SCHEMA": "",
        "SOURCE_DB_SCHEMA": "",
        "PWM_DRIVER": "mock",
    }
    env.pop("ZONE_NODE_IDS", None)
    if node_ids is not None:
        env["ZONE_NODE_IDS"] = node_ids
    return subprocess.run(
        [sys.executable, str(BOOTSTRAP)], cwd=ROOT, env=env, capture_output=True, text=True
    )


def _nodes(db_path: Path):
    with sqlite3.connect(db_path) as db:
        return dict(db.execute("SELECT node_id, is_active FROM zone_nodes ORDER BY node_id"))


def test_default_registers_two_nodes(tmp_path):
    db_path = tmp_path / "wsn.db"
    result = _bootstrap(db_path)
    assert result.returncode == 0, result.stderr
    assert _nodes(db_path) == {"NODE-01": 1, "NODE-02": 1}


def test_extra_node_is_deactivated_not_deleted(tmp_path):
    db_path = tmp_path / "wsn.db"
    assert _bootstrap(db_path, "NODE-01,NODE-02,NODE-03").returncode == 0
    assert _nodes(db_path) == {"NODE-01": 1, "NODE-02": 1, "NODE-03": 1}

    assert _bootstrap(db_path).returncode == 0
    assert _nodes(db_path) == {"NODE-01": 1, "NODE-02": 1, "NODE-03": 0}

    # Node ketiga dapat diaktifkan kembali; format angka juga diterima.
    assert _bootstrap(db_path, "1, 2, 3").returncode == 0
    assert _nodes(db_path) == {"NODE-01": 1, "NODE-02": 1, "NODE-03": 1}
