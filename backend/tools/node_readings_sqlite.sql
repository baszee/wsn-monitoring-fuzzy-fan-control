-- Skema lokal untuk menguji adaptor M2 pada SQLite. Tidak memiliki DROP.
-- Database PostgreSQL bersama tetap memakai schema.sql milik M2.
CREATE TABLE IF NOT EXISTS node_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at DATETIME NOT NULL,
    node_id SMALLINT NOT NULL,
    seq INTEGER NOT NULL,
    adc INTEGER NOT NULL,
    vpin REAL NOT NULL,
    v0 REAL NOT NULL,
    dust_ugm3 REAL NOT NULL,
    temperature REAL,
    humidity REAL,
    pressure_hpa REAL,
    rssi SMALLINT NOT NULL,
    snr REAL NOT NULL,
    payload_raw BLOB NOT NULL
);

CREATE INDEX IF NOT EXISTS node_readings_node_time_idx
    ON node_readings (node_id, received_at);

