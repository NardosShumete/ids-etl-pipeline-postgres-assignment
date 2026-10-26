-- ==============================================================================
-- CIC-IDS-2017 Intrusion Detection System ETL Pipeline: Business Analytics
-- Target: PostgreSQL 14+
-- Scenario: Network Operations / SOC Analytics for Ethiopian ISP or Banking Core
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- QUERY 1: Attack vs. Benign Traffic Share
-- ------------------------------------------------------------------------------
-- BUSINESS MEANING:
-- High-level executive KPI measuring the overall threat exposure of the network.
-- Telecommunications and banking executives need to know what fraction of observed
-- network sessions represent legitimate client activity versus hostile intrusion
-- attempts, including volumetric traffic load (in Megabytes).
-- ------------------------------------------------------------------------------
SELECT 
    CASE 
        WHEN a.is_malicious THEN 'Malicious / Attack Traffic'
        ELSE 'Benign / Authorized Traffic'
    END AS traffic_classification,
    COUNT(f.id) AS total_flows,
    ROUND(
        (COUNT(f.id)::numeric / SUM(COUNT(f.id)) OVER ()) * 100.0, 
        2
    ) AS flow_share_pct,
    ROUND(
        SUM(f.total_length_of_fwd_packets + f.total_length_of_bwd_packets)::numeric / (1024.0 * 1024.0),
        2
    ) AS total_volume_mbytes,
    ROUND(
        AVG(f.flow_bytes_per_s)::numeric, 
        2
    ) AS avg_bytes_per_second
FROM flows f
JOIN attack_types a ON f.attack_type_id = a.id
GROUP BY a.is_malicious
ORDER BY total_flows DESC;


-- ------------------------------------------------------------------------------
-- QUERY 2: Top 10 Targeted Destination Ports for Attack Traffic
-- ------------------------------------------------------------------------------
-- BUSINESS MEANING:
-- Identifies the primary listening services and network daemons targeted by
-- external threat actors. By pinpointing which service ports experience the highest
-- attack volume (e.g. port 80/443 for web exploits, port 21/22 for credential brute-force),
-- network engineering and firewall teams can deploy specialized rate-limits or
-- access-control lists (ACLs) to shield core banking servers.
-- ------------------------------------------------------------------------------
SELECT 
    f.destination_port,
    CASE 
        WHEN f.destination_port = 80 THEN 'HTTP (Web Server)'
        WHEN f.destination_port = 443 THEN 'HTTPS (Encrypted Web)'
        WHEN f.destination_port = 21 THEN 'FTP (Control Channel)'
        WHEN f.destination_port = 22 THEN 'SSH (Remote Administration)'
        WHEN f.destination_port = 53 THEN 'DNS (Domain Resolution)'
        WHEN f.destination_port = 8080 THEN 'HTTP-Alt / Web Proxy'
        WHEN f.destination_port = 25 THEN 'SMTP (Mail Transfer)'
        ELSE 'Other / Ephemeral'
    END AS common_service_name,
    COUNT(f.id) AS attack_flow_count,
    ROUND(
        (COUNT(f.id)::numeric / SUM(COUNT(f.id)) OVER ()) * 100.0, 
        2
    ) AS percentage_of_all_attacks,
    STRING_AGG(DISTINCT a.label, ', ') AS observed_attack_types
FROM flows f
JOIN attack_types a ON f.attack_type_id = a.id
WHERE a.is_malicious = TRUE
GROUP BY f.destination_port
ORDER BY attack_flow_count DESC
LIMIT 10;


-- ------------------------------------------------------------------------------
-- QUERY 3: Behavioral Profiling: Average Flow Duration & Packet Volume
-- ------------------------------------------------------------------------------
-- BUSINESS MEANING:
-- Provides deep behavioral telemetry differentiating attack mechanisms from normal
-- baseline behavior. For example:
--   - Volumetric DDoS & DoS Hulk exhibit massive packet rates and short burst intervals.
--   - Slowloris and Slowhttptest exhibit abnormally long durations with minimal packet transfer.
--   - PortScan flows feature minimal packets (SYN probes) and near-zero duration.
-- These metrics guide anomaly-detection threshold tuning in Next-Gen Firewalls (NGFW).
-- ------------------------------------------------------------------------------
SELECT 
    a.label AS attack_type_label,
    a.category AS attack_category,
    COUNT(f.id) AS sample_size,
    ROUND(AVG(f.flow_duration) / 1000.0, 2) AS avg_duration_milliseconds,
    ROUND(AVG(f.total_fwd_packets), 1) AS avg_forward_packets,
    ROUND(AVG(f.total_bwd_packets), 1) AS avg_backward_packets,
    ROUND(AVG(f.total_length_of_fwd_packets), 1) AS avg_fwd_bytes,
    ROUND(AVG(f.flow_packets_per_s)::numeric, 1) AS avg_packets_per_second
FROM flows f
JOIN attack_types a ON f.attack_type_id = a.id
GROUP BY a.label, a.category
ORDER BY sample_size DESC;


-- ------------------------------------------------------------------------------
-- QUERY 4: Temporal Threat Intensity: Most Targeted Day & Source File
-- ------------------------------------------------------------------------------
-- BUSINESS MEANING:
-- Determines which weekday experienced the heaviest adversary aggression.
-- Security Operations Center (SOC) managers use temporal correlation to evaluate
-- threat campaigns against organizational work schedules, identify coordinated multi-day
-- reconnaissance-to-exploit sequences, and plan analyst shift capacity.
-- ------------------------------------------------------------------------------
SELECT 
    sf.capture_day,
    sf.file_name,
    COUNT(f.id) AS total_flows_observed,
    COUNT(f.id) FILTER (WHERE a.is_malicious = TRUE) AS malicious_attack_flows,
    COUNT(f.id) FILTER (WHERE a.is_malicious = FALSE) AS benign_flows,
    ROUND(
        (COUNT(f.id) FILTER (WHERE a.is_malicious = TRUE)::numeric / NULLIF(COUNT(f.id), 0)::numeric) * 100.0,
        2
    ) AS attack_ratio_pct
FROM source_files sf
JOIN flows f ON sf.id = f.source_file_id
JOIN attack_types a ON f.attack_type_id = a.id
GROUP BY sf.capture_day, sf.file_name
ORDER BY malicious_attack_flows DESC;


-- ------------------------------------------------------------------------------
-- QUERY 5: EXPLAIN ANALYZE Demonstration (Port-Targeted Threat Query)
-- ------------------------------------------------------------------------------
-- TECHNICAL PURPOSE:
-- Demonstrates the performance acceleration enabled by `idx_flows_destination_port`
-- and `idx_flows_attack_port`. Without indexes, PostgreSQL would perform an
-- expensive sequential scan over millions of rows on disk. With the B-Tree index,
-- the planner uses a Bitmap Index Scan, reducing disk page visits by over 90%.
-- ------------------------------------------------------------------------------
EXPLAIN (ANALYZE, BUFFERS, COSTS)
SELECT 
    f.destination_port,
    COUNT(*) AS total_hits
FROM flows f
WHERE f.destination_port = 80
GROUP BY f.destination_port;


-- ------------------------------------------------------------------------------
-- QUERY 6: EXPLAIN ANALYZE Demonstration (Attack Category Filter Query)
-- ------------------------------------------------------------------------------
-- TECHNICAL PURPOSE:
-- Demonstrates the optimization provided by `idx_flows_attack_type_id`.
-- The planner leverages an Index Scan on `attack_type_id` to quickly isolate
-- malicious rows rather than scanning millions of benign records sequentially.
-- ------------------------------------------------------------------------------
EXPLAIN (ANALYZE, BUFFERS, COSTS)
SELECT 
    a.label,
    COUNT(f.id) AS incident_count,
    ROUND(AVG(f.flow_duration) / 1000.0, 2) AS avg_duration_ms
FROM flows f
JOIN attack_types a ON f.attack_type_id = a.id
WHERE f.attack_type_id = 2  -- DoS Hulk
GROUP BY a.label;
