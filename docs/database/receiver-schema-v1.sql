-- Tabel yang diisi receiver.py. Jalankan sekali:
--   psql "host=localhost dbname=wsn_db user=wsn_user" -f schema.sql
-- IF NOT EXISTS: tabel yang sudah ada tidak diubah.

-- Satu baris tiap receiver.py dijalankan: konfigurasi radio dan label kondisi pengujian.
CREATE TABLE IF NOT EXISTS sesi_uji (
    id            BIGSERIAL PRIMARY KEY,
    mulai         TIMESTAMPTZ NOT NULL DEFAULT now(),
    selesai       TIMESTAMPTZ,
    mode          TEXT        NOT NULL CHECK (mode IN ('sensor', 'uji')),
    label         TEXT,                  -- mis. "50 m tanpa penghalang, sesi 1"
    freq_hz       INTEGER     NOT NULL,
    sf            SMALLINT    NOT NULL,
    bw_hz         INTEGER     NOT NULL,
    cr_denom      SMALLINT    NOT NULL,
    tx_power_dbm  SMALLINT    NOT NULL,
    versi_paket   SMALLINT    NOT NULL
);

-- Tabel "Valid": data sensor dari paket yang lolos CRC aplikasi. Sumber data dashboard.
CREATE TABLE IF NOT EXISTS paket_valid (
    id            BIGSERIAL PRIMARY KEY,
    sesi_uji_id   BIGINT      NOT NULL REFERENCES sesi_uji ON DELETE CASCADE,
    received_at   TIMESTAMPTZ NOT NULL,
    node_id       SMALLINT    NOT NULL,
    sesi          INTEGER     NOT NULL,  -- identitas sesi node (acak tiap node menyala)
    seq           INTEGER     NOT NULL,
    adc           INTEGER     NOT NULL,
    vpin          REAL        NOT NULL,  -- V di pin ADC ESP32
    v0            REAL        NOT NULL,  -- V keluaran GP2Y1010 sebelum pembagi tegangan
    dust_ugm3     REAL        NOT NULL,
    temperature   REAL,                  -- NULL bila BME280 gagal dibaca
    humidity      REAL,
    pressure_hpa  REAL,
    rssi          SMALLINT    NOT NULL,
    snr           REAL        NOT NULL,
    payload_raw   BYTEA       NOT NULL
);
CREATE INDEX IF NOT EXISTS paket_valid_node_time_idx ON paket_valid (node_id, received_at DESC);

-- Tabel "Invalid": log kegagalan pemeriksaan. Tidak dipakai sebagai data kualitas udara.
CREATE TABLE IF NOT EXISTS paket_invalid (
    id               BIGSERIAL PRIMARY KEY,
    sesi_uji_id      BIGINT      NOT NULL REFERENCES sesi_uji ON DELETE CASCADE,
    received_at      TIMESTAMPTZ NOT NULL,
    alasan           TEXT        NOT NULL CHECK (alasan IN ('crc', 'struktur')),
    node_dipoll      SMALLINT,              -- node yang sedang dipanggil; NULL bila di luar giliran
    node_id_terbaca  SMALLINT,              -- header apa adanya, bisa ikut rusak
    sesi_terbaca     INTEGER,
    seq_terbaca      INTEGER,
    crc_tx           INTEGER,               -- CRC kiriman pemancar
    crc_rx           INTEGER,               -- CRC hasil hitung ulang di base station
    crc_phy_ok       BOOLEAN,               -- status CRC bawaan SX1278; NULL bila paket tanpa CRC PHY
    rssi             SMALLINT    NOT NULL,
    snr              REAL        NOT NULL,
    payload_raw      BYTEA       NOT NULL
);

-- Tabel "Evaluasi": satu baris tiap paket yang teramati, valid maupun tidak.
CREATE TABLE IF NOT EXISTS evaluasi (
    id              BIGSERIAL PRIMARY KEY,
    sesi_uji_id     BIGINT      NOT NULL REFERENCES sesi_uji ON DELETE CASCADE,
    received_at     TIMESTAMPTZ NOT NULL,
    node_dipoll     SMALLINT,
    tipe            TEXT CHECK (tipe IN ('sensor', 'uji')),
    node_id         SMALLINT,              -- identitas hasil pemasangan; NULL bila tidak dapat ditentukan
    sesi            INTEGER,
    seq             INTEGER,
    panjang         SMALLINT    NOT NULL,  -- byte
    struktur_ok     BOOLEAN     NOT NULL,
    crc_app_ok      BOOLEAN     NOT NULL,
    crc_phy_ok      BOOLEAN,
    duplikat        BOOLEAN     NOT NULL,
    -- dasar penetapan node_id/sesi/seq: 'crc_valid' | 'header' | 'urutan'; NULL = tidak dapat ditentukan
    dasar_pasangan  TEXT,
    n_e             INTEGER,               -- bit berbeda; NULL bila tanpa referensi
    n_b             INTEGER,               -- bit yang dibandingkan
    ber             DOUBLE PRECISION,
    rssi            SMALLINT    NOT NULL,
    snr             REAL        NOT NULL,
    payload_raw     BYTEA       NOT NULL,  -- byte asli hasil penerimaan
    payload_ref     BYTEA                  -- bit referensi pemancar yang dibandingkan
);
CREATE INDEX IF NOT EXISTS evaluasi_sesi_idx ON evaluasi (sesi_uji_id, node_dipoll);

-- Kehilangan paket: poll yang tidak diikuti paket apa pun. Tidak masuk perhitungan BER.
CREATE TABLE IF NOT EXISTS paket_hilang (
    id           BIGSERIAL PRIMARY KEY,
    sesi_uji_id  BIGINT      NOT NULL REFERENCES sesi_uji ON DELETE CASCADE,
    waktu        TIMESTAMPTZ NOT NULL,
    node_id      SMALLINT    NOT NULL
);

-- Rekap per sesi dan node. BER gabungan = total bit berbeda / total bit dibandingkan.
CREATE OR REPLACE VIEW ringkasan_uji AS
WITH e AS (
    SELECT sesi_uji_id, node_dipoll AS node_id,
           count(*)                                AS paket_teramati,
           count(*) FILTER (WHERE crc_app_ok)      AS crc_valid,
           count(*) FILTER (WHERE NOT crc_app_ok)  AS crc_invalid,
           count(*) FILTER (WHERE duplikat)        AS duplikat,
           count(n_b)                              AS berpasangan,
           count(*) FILTER (WHERE tipe = 'uji' AND n_b IS NULL) AS tak_berpasangan,
           sum(n_e)                                AS n_e,
           sum(n_b)                                AS n_b,
           avg(rssi)                               AS rssi_rata,
           avg(snr)                                AS snr_rata
    FROM evaluasi WHERE node_dipoll IS NOT NULL GROUP BY 1, 2
), h AS (
    SELECT sesi_uji_id, node_id, count(*) AS paket_hilang FROM paket_hilang GROUP BY 1, 2
)
SELECT s.id AS sesi_uji_id, s.label, s.mode, s.mulai, s.sf, s.bw_hz, s.cr_denom,
       node_id,
       coalesce(e.paket_teramati, 0) + coalesce(h.paket_hilang, 0) AS poll_dikirim,
       coalesce(e.paket_teramati, 0) AS paket_teramati,
       coalesce(h.paket_hilang, 0)   AS paket_hilang,
       coalesce(e.crc_valid, 0)      AS crc_valid,
       coalesce(e.crc_invalid, 0)    AS crc_invalid,
       coalesce(e.duplikat, 0)       AS duplikat,
       coalesce(e.berpasangan, 0)    AS berpasangan,
       coalesce(e.tak_berpasangan, 0) AS tak_berpasangan,
       e.n_e, e.n_b,
       e.n_e::double precision / nullif(e.n_b, 0) AS ber_gabungan,
       round(e.rssi_rata, 1) AS rssi_rata,
       round(e.snr_rata::numeric, 1) AS snr_rata
FROM e FULL JOIN h USING (sesi_uji_id, node_id)
JOIN sesi_uji s ON s.id = sesi_uji_id
ORDER BY s.id, node_id;
