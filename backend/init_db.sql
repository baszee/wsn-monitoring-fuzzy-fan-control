-- =============================================================================
-- INTI BASIS DATA: SUBSISTEM 3 (MONITORING & KONTROL FAN BERBASIS FUZZY WSN)
-- Skrip DDL PostgreSQL untuk Tabel Aplikasi & Tabel Tiruan Subsistem Penerima M2
-- =============================================================================

-- Bersihkan tabel jika sudah ada (urutan penghapusan memperhatikan relasi foreign key)
DROP TABLE IF EXISTS zone_controls CASCADE;
DROP TABLE IF EXISTS fuzzy_results CASCADE;
DROP TABLE IF EXISTS zone_nodes CASCADE;
DROP TABLE IF EXISTS control_config CASCADE;
DROP TABLE IF EXISTS mock_receiver_valid_data CASCADE;

-- -----------------------------------------------------------------------------
-- 1. TABEL APLIKASI
-- -----------------------------------------------------------------------------

-- Tabel: zone_nodes
-- Menyimpan pemetaan node sensor yang terdaftar pada zona pemantauan tertentu
CREATE TABLE zone_nodes (
    zone_node_id SERIAL PRIMARY KEY,
    zone_id VARCHAR(50) NOT NULL,
    node_id VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_zone_node UNIQUE (zone_id, node_id)
);

-- Tabel: control_config
-- Menyimpan versi konfigurasi inferensi fuzzy, rentang sensor, dan parameter pemetaan PWM
CREATE TABLE control_config (
    config_version VARCHAR(50) PRIMARY KEY,
    membership_params JSONB NOT NULL,
    rule_base JSONB NOT NULL,
    dust_low_reference DOUBLE PRECISION NOT NULL,
    dust_high_reference DOUBLE PRECISION NOT NULL,
    u_off DOUBLE PRECISION NOT NULL,
    u_max DOUBLE PRECISION NOT NULL,
    d_min DOUBLE PRECISION NOT NULL,
    delta_d_update DOUBLE PRECISION NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tabel: fuzzy_results
-- Menyimpan hasil inferensi Fuzzy Mamdani per node (skor kondisi s_i & tingkat kendali u_i)
CREATE TABLE fuzzy_results (
    fuzzy_result_id BIGSERIAL PRIMARY KEY,
    zone_node_id INTEGER NOT NULL REFERENCES zone_nodes(zone_node_id) ON DELETE CASCADE,
    config_version VARCHAR(50) NOT NULL REFERENCES control_config(config_version),
    processing_cycle_id VARCHAR(100) NOT NULL,
    source_record_id BIGINT NOT NULL,
    source_timestamp TIMESTAMPTZ NOT NULL,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    dust_raw_voltage DOUBLE PRECISION,
    dust_index DOUBLE PRECISION NOT NULL,
    condition_score DOUBLE PRECISION NOT NULL,
    condition_class VARCHAR(50) NOT NULL,
    control_level DOUBLE PRECISION NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_fuzzy_node_record_cfg UNIQUE (zone_node_id, source_record_id, config_version)
);

-- Tabel: zone_controls
-- Menyimpan keputusan kendali zona agregasi (u_zona = max u_i) dan perintah PWM duty cycle
CREATE TABLE zone_controls (
    zone_control_id BIGSERIAL PRIMARY KEY,
    config_version VARCHAR(50) NOT NULL REFERENCES control_config(config_version),
    processing_cycle_id VARCHAR(100) NOT NULL,
    zone_id VARCHAR(50) NOT NULL,
    control_fuzzy_result_id BIGINT REFERENCES fuzzy_results(fuzzy_result_id) ON DELETE SET NULL,
    control_node_id VARCHAR(50),
    zone_control_level DOUBLE PRECISION,
    pwm_command_percent DOUBLE PRECISION NOT NULL,
    candidate_pwm_percent DOUBLE PRECISION,
    previous_pwm_percent DOUBLE PRECISION,
    auto_pwm_percent DOUBLE PRECISION,
    hysteresis_held BOOLEAN NOT NULL DEFAULT FALSE,
    control_status VARCHAR(50) NOT NULL,
    fan_command_status VARCHAR(50) NOT NULL,
    control_mode VARCHAR(20) NOT NULL DEFAULT 'auto',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 2. TABEL TIRUAN SUBSISTEM PENERIMA M2 (MOCK RECEIVER)
-- -----------------------------------------------------------------------------

-- Tabel: mock_receiver_valid_data
-- Meniru tabel penyimpanan data sensor valid dari Subsistem 2 (Penerima LoRa / Gateway)
CREATE TABLE mock_receiver_valid_data (
    id BIGSERIAL PRIMARY KEY,
    node_id VARCHAR(50) NOT NULL,
    temperature DOUBLE PRECISION NOT NULL,
    humidity DOUBLE PRECISION NOT NULL,
    dust_raw_voltage DOUBLE PRECISION NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status_valid BOOLEAN NOT NULL DEFAULT TRUE
);

-- -----------------------------------------------------------------------------
-- INDEKS PERFORMA
-- -----------------------------------------------------------------------------
CREATE INDEX idx_fuzzy_results_cycle ON fuzzy_results(processing_cycle_id);
CREATE INDEX idx_fuzzy_results_node_time ON fuzzy_results(zone_node_id, processed_at DESC);
CREATE INDEX idx_zone_controls_cycle ON zone_controls(processing_cycle_id);
CREATE INDEX idx_zone_controls_created ON zone_controls(created_at DESC);
CREATE INDEX idx_mock_receiver_node_time ON mock_receiver_valid_data(node_id, timestamp DESC);
