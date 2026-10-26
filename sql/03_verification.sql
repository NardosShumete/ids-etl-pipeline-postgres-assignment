-- ==============================================================================
-- CIC-IDS-2017 Intrusion Detection System ETL Pipeline: Verification Queries
-- Purpose: Audit database row counts, partition alignment, referential integrity,
--          attack taxonomy distribution, and absence of NULL values.
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Total Rows in flows, flow_statistics, and Partition Synchronization
-- Validates that the 1:1 vertical partition maintained equal cardinality (2M+ rows).
-- ------------------------------------------------------------------------------
SELECT 
    (SELECT COUNT(*) FROM flows) AS total_flows,
    (SELECT COUNT(*) FROM flow_statistics) AS total_flow_statistics,
    ((SELECT COUNT(*) FROM flows) - (SELECT COUNT(*) FROM flow_statistics)) AS partition_delta;

-- ------------------------------------------------------------------------------
-- 2. Ingested Rows per Source File (Audit Lineage & Consistency)
-- Compares tracked metadata in source_files against actual foreign-keyed rows in flows.
-- ------------------------------------------------------------------------------
SELECT 
    sf.id AS source_file_id,
    sf.file_name,
    sf.capture_day,
    sf.row_count AS logged_row_count,
    COUNT(f.id) AS actual_flows_in_db,
    (sf.row_count - COUNT(f.id)) AS discrepancy,
    sf.imported_at
FROM source_files sf
LEFT JOIN flows f ON sf.id = f.source_file_id
GROUP BY sf.id, sf.file_name, sf.capture_day, sf.row_count, sf.imported_at
ORDER BY sf.id;

-- ------------------------------------------------------------------------------
-- 3. Distribution by Attack Type & Malicious Classification
-- Calculates flow counts and exact percentage shares across all 15 attack classes.
-- ------------------------------------------------------------------------------
SELECT 
    a.id AS attack_type_id,
    a.label,
    a.category,
    a.is_malicious,
    COUNT(f.id) AS total_flows,
    ROUND(
        (COUNT(f.id)::numeric / NULLIF((SELECT COUNT(*) FROM flows), 0)::numeric) * 100.0, 
        4
    ) AS percentage_of_total
FROM attack_types a
LEFT JOIN flows f ON a.id = f.attack_type_id
GROUP BY a.id, a.label, a.category, a.is_malicious
ORDER BY total_flows DESC;

-- ------------------------------------------------------------------------------
-- 3b. Attack Label Encoding & Quality Validation
-- Verifies no leading/trailing whitespace, no replacement characters, and valid characters.
-- ------------------------------------------------------------------------------
SELECT 
    COUNT(*) FILTER (WHERE label != TRIM(label)) AS labels_with_whitespace,
    COUNT(*) FILTER (WHERE label ~ '[^A-Za-z0-9 _-]') AS labels_with_invalid_chars,
    COUNT(*) FILTER (WHERE POSITION(chr(65533) IN label) > 0) AS labels_with_replacement_chars
FROM attack_types;

-- ------------------------------------------------------------------------------
-- 4. Orphan Foreign Key Check (Referential Integrity Audit)
-- Must return 0 across all checks, proving complete referential integrity.
-- ------------------------------------------------------------------------------
SELECT 
    (SELECT COUNT(*) 
     FROM flows f 
     LEFT JOIN source_files sf ON f.source_file_id = sf.id 
     WHERE sf.id IS NULL) AS orphan_source_files_count,

    (SELECT COUNT(*) 
     FROM flows f 
     LEFT JOIN attack_types a ON f.attack_type_id = a.id 
     WHERE a.id IS NULL) AS orphan_attack_types_count,

    (SELECT COUNT(*) 
     FROM flows f 
     LEFT JOIN flow_statistics fs ON f.id = fs.flow_id 
     WHERE fs.flow_id IS NULL) AS flows_missing_statistics_count,

    (SELECT COUNT(*) 
     FROM flow_statistics fs 
     LEFT JOIN flows f ON fs.flow_id = f.id 
     WHERE f.id IS NULL) AS statistics_missing_flow_count;

-- ------------------------------------------------------------------------------
-- 5. NULL Value Integrity Audit Across Critical Telemetry
-- Verifies no NULLs were ingested in essential connection and volume attributes.
-- ------------------------------------------------------------------------------
SELECT 
    COUNT(*) FILTER (WHERE id IS NULL) AS null_ids,
    COUNT(*) FILTER (WHERE source_file_id IS NULL) AS null_source_file_ids,
    COUNT(*) FILTER (WHERE attack_type_id IS NULL) AS null_attack_type_ids,
    COUNT(*) FILTER (WHERE destination_port IS NULL) AS null_destination_ports,
    COUNT(*) FILTER (WHERE flow_duration IS NULL) AS null_flow_durations,
    COUNT(*) FILTER (WHERE total_fwd_packets IS NULL) AS null_total_fwd_packets,
    COUNT(*) FILTER (WHERE total_bwd_packets IS NULL) AS null_total_bwd_packets,
    COUNT(*) FILTER (WHERE flow_bytes_per_s IS NULL) AS null_flow_bytes_per_s,
    COUNT(*) FILTER (WHERE flow_packets_per_s IS NULL) AS null_flow_packets_per_s
FROM flows;
