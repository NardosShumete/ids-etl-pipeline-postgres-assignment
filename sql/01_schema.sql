-- ==============================================================================
-- CIC-IDS-2017 Intrusion Detection System ETL Pipeline: Database Schema
-- Target: PostgreSQL 14+
-- Scenario: Network Operations / SOC Analytics for ISP / Financial Infrastructure
-- ==============================================================================

-- Drop existing tables in reverse dependency order to ensure idempotency
DROP TABLE IF EXISTS flow_statistics CASCADE;
DROP TABLE IF EXISTS flows CASCADE;
DROP TABLE IF EXISTS source_files CASCADE;
DROP TABLE IF EXISTS attack_types CASCADE;

-- ------------------------------------------------------------------------------
-- 1. attack_types (Lookup / Dimension Table)
-- Normalizes categorical attack taxonomy (15+ classes), decoupling text labels
-- from high-volume flow rows to optimize storage and enforce 3NF.
-- ------------------------------------------------------------------------------
CREATE TABLE attack_types (
    id SMALLSERIAL PRIMARY KEY,
    label VARCHAR(64) NOT NULL UNIQUE,
    category VARCHAR(32) NOT NULL,
    is_malicious BOOLEAN NOT NULL DEFAULT FALSE,
    description TEXT
);

COMMENT ON TABLE attack_types IS 'Lookup dimension mapping network flow labels to standardized threat categories';
COMMENT ON COLUMN attack_types.label IS 'Exact string label as reported by IDS or flow generator (e.g., BENIGN, DoS Hulk)';
COMMENT ON COLUMN attack_types.category IS 'High-level threat classification (e.g., Benign, DoS, DDoS, PortScan, Brute-Force, Web Attack, Bot, Infiltration, Heartbleed)';
COMMENT ON COLUMN attack_types.is_malicious IS 'Boolean flag indicating whether the flow represents malicious adversary activity';

-- ------------------------------------------------------------------------------
-- 2. source_files (ETL Audit and Lineage Table)
-- Tracks source CSV file metadata, ingest lineage, and record counts for auditability.
-- ------------------------------------------------------------------------------
CREATE TABLE source_files (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL UNIQUE,
    capture_day VARCHAR(32),
    row_count BIGINT DEFAULT 0 CHECK (row_count >= 0),
    imported_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE source_files IS 'Tracks source dataset files, ingestion timestamps, and raw row counts for lineage';
COMMENT ON COLUMN source_files.file_name IS 'Base filename of the raw CSV file extracted from CIC-IDS-2017';
COMMENT ON COLUMN source_files.capture_day IS 'Weekday of packet capture during dataset generation (e.g., Monday, Tuesday)';

-- ------------------------------------------------------------------------------
-- 3. flows (Core Transactional Telemetry Table)
-- Stores primary network flow indicators, connection endpoints, duration,
-- byte/packet totals, rates, and primary TCP control flags.
-- Designed for high-frequency filtering, SOC dashboard queries, and rule evaluation.
-- ------------------------------------------------------------------------------
CREATE TABLE flows (
    id BIGSERIAL PRIMARY KEY,
    source_file_id INT NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
    attack_type_id SMALLINT NOT NULL REFERENCES attack_types(id) ON DELETE RESTRICT,
    destination_port INTEGER NOT NULL CHECK (destination_port >= 0 AND destination_port <= 65535),
    flow_duration BIGINT NOT NULL CHECK (flow_duration >= 0),
    total_fwd_packets BIGINT NOT NULL CHECK (total_fwd_packets >= 0),
    total_bwd_packets BIGINT NOT NULL CHECK (total_bwd_packets >= 0),
    total_length_of_fwd_packets BIGINT NOT NULL CHECK (total_length_of_fwd_packets >= 0),
    total_length_of_bwd_packets BIGINT NOT NULL CHECK (total_length_of_bwd_packets >= 0),
    flow_bytes_per_s DOUBLE PRECISION,
    flow_packets_per_s DOUBLE PRECISION,
    flow_iat_mean DOUBLE PRECISION,
    flow_iat_std DOUBLE PRECISION,
    flow_iat_max DOUBLE PRECISION,
    flow_iat_min DOUBLE PRECISION,
    fin_flag_count SMALLINT NOT NULL DEFAULT 0 CHECK (fin_flag_count >= 0),
    syn_flag_count SMALLINT NOT NULL DEFAULT 0 CHECK (syn_flag_count >= 0),
    rst_flag_count SMALLINT NOT NULL DEFAULT 0 CHECK (rst_flag_count >= 0),
    psh_flag_count SMALLINT NOT NULL DEFAULT 0 CHECK (psh_flag_count >= 0),
    ack_flag_count SMALLINT NOT NULL DEFAULT 0 CHECK (ack_flag_count >= 0),
    urg_flag_count SMALLINT NOT NULL DEFAULT 0 CHECK (urg_flag_count >= 0),
    cwe_flag_count SMALLINT NOT NULL DEFAULT 0 CHECK (cwe_flag_count >= 0),
    ece_flag_count SMALLINT NOT NULL DEFAULT 0 CHECK (ece_flag_count >= 0),
    down_up_ratio DOUBLE PRECISION CHECK (down_up_ratio >= 0),
    average_packet_size DOUBLE PRECISION CHECK (average_packet_size >= 0)
);

COMMENT ON TABLE flows IS 'Primary network flow telemetry records containing connection endpoints and core flow volume';
COMMENT ON COLUMN flows.destination_port IS 'Destination TCP/UDP service port (0-65535)';
COMMENT ON COLUMN flows.flow_duration IS 'Total duration of the bidirectional flow in microseconds';
COMMENT ON COLUMN flows.total_fwd_packets IS 'Total number of packets transmitted in the forward direction (source to dest)';
COMMENT ON COLUMN flows.total_bwd_packets IS 'Total number of packets transmitted in the backward direction (dest to source)';

-- ------------------------------------------------------------------------------
-- 4. flow_statistics (Detailed Flow Metrics Table - 1:1 Partition)
-- Vertically partitioned from the core `flows` table to maintain compact row
-- widths in PostgreSQL buffer cache pages. Holds deep packet length distributions,
-- directional IATs, TCP window metrics, subflow stats, and active/idle state timing.
-- ------------------------------------------------------------------------------
CREATE TABLE flow_statistics (
    flow_id BIGINT PRIMARY KEY REFERENCES flows(id) ON DELETE CASCADE,
    
    -- Packet Length Distributions
    fwd_packet_length_max DOUBLE PRECISION CHECK (fwd_packet_length_max >= 0),
    fwd_packet_length_min DOUBLE PRECISION CHECK (fwd_packet_length_min >= 0),
    fwd_packet_length_mean DOUBLE PRECISION CHECK (fwd_packet_length_mean >= 0),
    fwd_packet_length_std DOUBLE PRECISION CHECK (fwd_packet_length_std >= 0),
    bwd_packet_length_max DOUBLE PRECISION CHECK (bwd_packet_length_max >= 0),
    bwd_packet_length_min DOUBLE PRECISION CHECK (bwd_packet_length_min >= 0),
    bwd_packet_length_mean DOUBLE PRECISION CHECK (bwd_packet_length_mean >= 0),
    bwd_packet_length_std DOUBLE PRECISION CHECK (bwd_packet_length_std >= 0),
    min_packet_length DOUBLE PRECISION CHECK (min_packet_length >= 0),
    max_packet_length DOUBLE PRECISION CHECK (max_packet_length >= 0),
    packet_length_mean DOUBLE PRECISION CHECK (packet_length_mean >= 0),
    packet_length_std DOUBLE PRECISION CHECK (packet_length_std >= 0),
    packet_length_variance DOUBLE PRECISION CHECK (packet_length_variance >= 0),

    -- Directional Inter-Arrival Times (IAT)
    fwd_iat_total DOUBLE PRECISION CHECK (fwd_iat_total >= 0),
    fwd_iat_mean DOUBLE PRECISION CHECK (fwd_iat_mean >= 0),
    fwd_iat_std DOUBLE PRECISION CHECK (fwd_iat_std >= 0),
    fwd_iat_max DOUBLE PRECISION CHECK (fwd_iat_max >= 0),
    fwd_iat_min DOUBLE PRECISION CHECK (fwd_iat_min >= 0),
    bwd_iat_total DOUBLE PRECISION CHECK (bwd_iat_total >= 0),
    bwd_iat_mean DOUBLE PRECISION CHECK (bwd_iat_mean >= 0),
    bwd_iat_std DOUBLE PRECISION CHECK (bwd_iat_std >= 0),
    bwd_iat_max DOUBLE PRECISION CHECK (bwd_iat_max >= 0),
    bwd_iat_min DOUBLE PRECISION CHECK (bwd_iat_min >= 0),

    -- Segment, Header & Rate Metrics
    fwd_psh_flags SMALLINT CHECK (fwd_psh_flags >= 0),
    bwd_psh_flags SMALLINT CHECK (bwd_psh_flags >= 0),
    fwd_urg_flags SMALLINT CHECK (fwd_urg_flags >= 0),
    bwd_urg_flags SMALLINT CHECK (bwd_urg_flags >= 0),
    fwd_header_length BIGINT,
    bwd_header_length BIGINT,
    fwd_packets_per_s DOUBLE PRECISION,
    bwd_packets_per_s DOUBLE PRECISION,
    avg_fwd_segment_size DOUBLE PRECISION CHECK (avg_fwd_segment_size >= 0),
    avg_bwd_segment_size DOUBLE PRECISION CHECK (avg_bwd_segment_size >= 0),
    fwd_header_length_1 BIGINT,

    -- Bulk Transfer Metrics
    fwd_avg_bytes_bulk DOUBLE PRECISION CHECK (fwd_avg_bytes_bulk >= 0),
    fwd_avg_packets_bulk DOUBLE PRECISION CHECK (fwd_avg_packets_bulk >= 0),
    fwd_avg_bulk_rate DOUBLE PRECISION CHECK (fwd_avg_bulk_rate >= 0),
    bwd_avg_bytes_bulk DOUBLE PRECISION CHECK (bwd_avg_bytes_bulk >= 0),
    bwd_avg_packets_bulk DOUBLE PRECISION CHECK (bwd_avg_packets_bulk >= 0),
    bwd_avg_bulk_rate DOUBLE PRECISION CHECK (bwd_avg_bulk_rate >= 0),

    -- Subflows and TCP Window Metrics
    subflow_fwd_packets BIGINT CHECK (subflow_fwd_packets >= 0),
    subflow_fwd_bytes BIGINT CHECK (subflow_fwd_bytes >= 0),
    subflow_bwd_packets BIGINT CHECK (subflow_bwd_packets >= 0),
    subflow_bwd_bytes BIGINT CHECK (subflow_bwd_bytes >= 0),
    init_win_bytes_forward BIGINT,
    init_win_bytes_backward BIGINT,
    act_data_pkt_fwd BIGINT CHECK (act_data_pkt_fwd >= 0),
    min_seg_size_forward BIGINT,

    -- Active / Idle Connection Timing
    active_mean DOUBLE PRECISION CHECK (active_mean >= 0),
    active_std DOUBLE PRECISION CHECK (active_std >= 0),
    active_max DOUBLE PRECISION CHECK (active_max >= 0),
    active_min DOUBLE PRECISION CHECK (active_min >= 0),
    idle_mean DOUBLE PRECISION CHECK (idle_mean >= 0),
    idle_std DOUBLE PRECISION CHECK (idle_std >= 0),
    idle_max DOUBLE PRECISION CHECK (idle_max >= 0),
    idle_min DOUBLE PRECISION CHECK (idle_min >= 0)
);

COMMENT ON TABLE flow_statistics IS 'Secondary 1:1 table storing granular statistical distributions, subflow aggregates, and timing';

-- ------------------------------------------------------------------------------
-- 5. Seed attack_types Lookup Table
-- Populates all known attack labels across the CIC-IDS-2017 dataset
-- ------------------------------------------------------------------------------
INSERT INTO attack_types (label, category, is_malicious, description) VALUES
('BENIGN', 'Benign', FALSE, 'Normal, authorized background network traffic across campus and enterprise workstations'),
('DoS Hulk', 'DoS', TRUE, 'HTTP Unbearable Load King: High-volume application-layer DoS flooding with dynamic randomized request URLs'),
('PortScan', 'PortScan', TRUE, 'Probing host TCP/UDP ports to discover open listening services and perimeter vulnerabilities'),
('DDoS', 'DDoS', TRUE, 'Distributed Denial of Service attack overwhelming target network bandwidth and socket buffers'),
('DoS GoldenEye', 'DoS', TRUE, 'Layer 7 DoS attack issuing persistent keep-alive HTTP GET/POST requests with cache-busting headers'),
('FTP-Patator', 'Brute-Force', TRUE, 'Multi-threaded brute-force password guessing targeting File Transfer Protocol (FTP) servers'),
('SSH-Patator', 'Brute-Force', TRUE, 'Multi-threaded brute-force password guessing targeting Secure Shell (SSH) daemons'),
('DoS slowloris', 'DoS', TRUE, 'Low-bandwidth Layer 7 attack keeping hundreds of HTTP connections open by slowly transmitting incomplete headers'),
('DoS Slowhttptest', 'DoS', TRUE, 'Slow HTTP POST / Slow Read attack exhausting web server connection pools and memory'),
('Bot', 'Bot', TRUE, 'Compromised workstation participating in Ares botnet command and control (C2) communication'),
('Web Attack - Brute Force', 'Web Attack', TRUE, 'Automated dictionary and credential stuffing attack against web application authentication forms'),
('Web Attack - XSS', 'Web Attack', TRUE, 'Cross-Site Scripting attack injecting malicious client-side JavaScript payloads into web forms'),
('Web Attack - Sql Injection', 'Web Attack', TRUE, 'SQL injection exploitation attempting unauthorized relational database access, bypass, or exfiltration'),
('Infiltration', 'Infiltration', TRUE, 'Post-exploitation lateral movement and malware payload staging across internal network subnets'),
('Heartbleed', 'Heartbleed', TRUE, 'Exploitation of OpenSSL TLS heartbeat extension buffer over-read (CVE-2014-0160) to leak private keys and memory')
ON CONFLICT (label) DO UPDATE 
SET category = EXCLUDED.category,
    is_malicious = EXCLUDED.is_malicious,
    description = EXCLUDED.description;
