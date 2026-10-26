-- ==============================================================================
-- CIC-IDS-2017 Intrusion Detection System ETL Pipeline: Post-Load Indexes
-- Target: PostgreSQL 14+
-- ==============================================================================
-- NOTE ON BULK INGESTION PERFORMANCE:
-- In relational databases (PostgreSQL), indexes should be constructed AFTER
-- the bulk loading phase when dealing with millions of records (~2.83M flows).
-- 
-- Why post-load indexing is critical:
-- 1. Ingestion Speed: Loading data into an unindexed table is a sequential append
--    operation (optimized via COPY / COPY FROM STDIN), reaching tens of thousands
--    of rows per second.
-- 2. Reduced WAL Write Amplification: Inserting row-by-row into indexed tables
--    triggers continuous B-Tree leaf node splits and massive write-ahead log (WAL)
--    traffic.
-- 3. Optimal B-Tree Structure: Creating the index over sorted, in-memory data
--    yields compact, fully packed B-Tree pages with 0% fragmentation.
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Core Foreign Key Indexes (flows table)
-- Accelerates JOINs between flows, attack_types, and source_files
-- ------------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_flows_attack_type_id 
    ON flows (attack_type_id);

CREATE INDEX IF NOT EXISTS idx_flows_source_file_id 
    ON flows (source_file_id);

-- ------------------------------------------------------------------------------
-- 2. Network Endpoint and Operational Indexes (flows table)
-- Accelerates filtering by destination service ports (e.g., port 80 HTTP, 22 SSH)
-- ------------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_flows_destination_port 
    ON flows (destination_port);

CREATE INDEX IF NOT EXISTS idx_flows_duration 
    ON flows (flow_duration);

-- ------------------------------------------------------------------------------
-- 3. Composite Threat Hunting Index (flows table)
-- Supports compound analytical queries filtering by attack category/type
-- and specific targeted port numbers (e.g. DoS Hulk against port 80/443).
-- ------------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_flows_attack_port 
    ON flows (attack_type_id, destination_port);

-- ------------------------------------------------------------------------------
-- 4. Auxiliary Dimension Indexes
-- Accelerates lookups on high-level attack categories and capture metadata
-- ------------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_attack_types_category 
    ON attack_types (category);

CREATE INDEX IF NOT EXISTS idx_source_files_capture_day 
    ON source_files (capture_day);
