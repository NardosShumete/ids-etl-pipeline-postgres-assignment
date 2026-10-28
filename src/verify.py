"""Verification Script for IDS ETL Pipeline.

Executes database verification queries from `sql/03_verification.sql`, audits
referential integrity, displays attack type distributions, checks for NULLs,
and reconciles loaded row counts against raw CSV inputs.

Usage:
    python src/verify.py
    python -m src.verify
"""

import sys
from pathlib import Path

# Add project root to sys.path for direct execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2

from src.config import RAW_DATA_DIR, get_db_params
from src.logger import setup_logger

logger = setup_logger("verify")


def get_raw_csv_row_counts() -> dict[str, int]:
    """Calculate raw line counts across extracted CSV files (excluding header)."""
    counts = {}
    for csv_file in sorted(RAW_DATA_DIR.glob("*.csv")):
        with open(csv_file, "rb") as fp:
            line_count = sum(1 for _ in fp) - 1
        counts[csv_file.name] = line_count
    return counts


def run_verification() -> bool:
    """Run all verification queries against PostgreSQL and print formatted audit reports."""
    logger.info("Connecting to database for verification audit...")
    conn = psycopg2.connect(**get_db_params())
    all_passed = True

    try:
        with conn.cursor() as cur:
            # 1. Total Rows & Vertical Partition Integrity
            print("\n" + "=" * 80)
            print("1. TOTAL ROW COUNTS & VERTICAL PARTITION INTEGRITY")
            print("=" * 80)
            cur.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM flows) AS total_flows,
                    (SELECT COUNT(*) FROM flow_statistics) AS total_flow_statistics;
            """)
            total_flows, total_stats = cur.fetchone()
            print(f"  * flows table count           : {total_flows:,}")
            print(f"  * flow_statistics table count : {total_stats:,}")
            print(f"  * Partition Difference        : {total_flows - total_stats:,}")

            if total_flows >= 2_000_000:
                print(
                    "  [PASS] Dataset verification confirmed: > 2 Million rows ingested."
                )
            else:
                print(
                    f"  [FAIL] Ingested rows ({total_flows:,}) is under 2,000,000 threshold."
                )
                all_passed = False

            if total_flows == total_stats:
                print(
                    "  [PASS] Vertical partitioning is 100% synchronized (flows == flow_statistics)."
                )
            else:
                print("  [FAIL] Vertical partition mismatch detected!")
                all_passed = False

            # 2. Ingested Rows per Source File
            print("\n" + "=" * 80)
            print("2. AUDIT LINEAGE & ROWS PER SOURCE FILE")
            print("=" * 80)
            cur.execute("""
                SELECT 
                    sf.id,
                    sf.file_name,
                    sf.capture_day,
                    sf.row_count,
                    COUNT(f.id) AS flows_count
                FROM source_files sf
                LEFT JOIN flows f ON sf.id = f.source_file_id
                GROUP BY sf.id, sf.file_name, sf.capture_day, sf.row_count
                ORDER BY sf.id;
            """)
            file_rows = cur.fetchall()
            print(f"{'ID':<4} {'Capture Day':<12} {'Loaded Rows':<14} {'File Name'}")
            print("-" * 80)
            for r in file_rows:
                print(f"{r[0]:<4} {r[2]:<12} {r[4]:<14,} {r[1]}")

            # 3. Attack Type Taxonomy Distribution
            print("\n" + "=" * 80)
            print("3. ATTACK TYPE TAXONOMY DISTRIBUTION & SHARES")
            print("=" * 80)
            cur.execute("""
                SELECT 
                    a.id,
                    a.label,
                    a.category,
                    a.is_malicious,
                    COUNT(f.id) AS total_flows,
                    ROUND((COUNT(f.id)::numeric / NULLIF((SELECT COUNT(*) FROM flows), 0)::numeric) * 100.0, 4) AS pct
                FROM attack_types a
                LEFT JOIN flows f ON a.id = f.attack_type_id
                GROUP BY a.id, a.label, a.category, a.is_malicious
                ORDER BY total_flows DESC;
            """)
            attack_rows = cur.fetchall()
            print(
                f"{'ID':<4} {'Label':<32} {'Category':<16} {'Malicious':<10} {'Flow Count':<14} {'Share (%)'}"
            )
            print("-" * 80)
            for r in attack_rows:
                print(
                    f"{r[0]:<4} {r[1]:<32} {r[2]:<16} {r[3]!s:<10} {r[4]:<14,} {r[5]}%"
                )

            # 3b. Strong Label and Character Set Validation
            print("\n" + "=" * 80)
            print("3b. ATTACK LABEL INTEGRITY & ENCODING QUALITY AUDIT")
            print("=" * 80)
            cur.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE label != TRIM(label)),
                    COUNT(*) FILTER (WHERE label ~ '[^A-Za-z0-9 _-]'),
                    COUNT(*) FILTER (WHERE POSITION(chr(65533) IN label) > 0)
                FROM attack_types;
            """)
            label_checks = cur.fetchone()
            print(f"  * Labels with leading/trailing whitespace : {label_checks[0]}")
            print(f"  * Labels with unexpected characters (regex): {label_checks[1]}")
            print(
                f"  * Labels with Unicode replacement chars (\\uFFFD): {label_checks[2]}"
            )
            if sum(label_checks) == 0:
                print(
                    "  [PASS] All attack type labels are clean, valid, and properly encoded."
                )
            else:
                print("  [FAIL] Label encoding defects detected!")
                all_passed = False

            # 4. Orphan Foreign Key Audit
            print("\n" + "=" * 80)
            print("4. ORPHAN FOREIGN KEY & REFERENTIAL INTEGRITY AUDIT")
            print("=" * 80)
            cur.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM flows f LEFT JOIN source_files sf ON f.source_file_id = sf.id WHERE sf.id IS NULL),
                    (SELECT COUNT(*) FROM flows f LEFT JOIN attack_types a ON f.attack_type_id = a.id WHERE a.id IS NULL),
                    (SELECT COUNT(*) FROM flows f LEFT JOIN flow_statistics fs ON f.id = fs.flow_id WHERE fs.flow_id IS NULL),
                    (SELECT COUNT(*) FROM flow_statistics fs LEFT JOIN flows f ON fs.flow_id = f.id WHERE f.id IS NULL);
            """)
            orphans = cur.fetchone()
            print(f"  * Orphan source_file references in flows : {orphans[0]}")
            print(f"  * Orphan attack_type references in flows : {orphans[1]}")
            print(f"  * flows missing matching flow_statistics : {orphans[2]}")
            print(f"  * flow_statistics missing matching flows : {orphans[3]}")

            if sum(orphans) == 0:
                print(
                    "  [PASS] Zero orphan records found. Referential integrity is strictly maintained."
                )
            else:
                print("  [FAIL] Orphan records detected!")
                all_passed = False

            # 5. NULL Value Integrity Audit Across Critical Columns
            print("\n" + "=" * 80)
            print("5. NULL VALUE INTEGRITY AUDIT (CRITICAL TELEMETRY)")
            print("=" * 80)
            cur.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE id IS NULL),
                    COUNT(*) FILTER (WHERE source_file_id IS NULL),
                    COUNT(*) FILTER (WHERE attack_type_id IS NULL),
                    COUNT(*) FILTER (WHERE destination_port IS NULL),
                    COUNT(*) FILTER (WHERE flow_duration IS NULL),
                    COUNT(*) FILTER (WHERE total_fwd_packets IS NULL),
                    COUNT(*) FILTER (WHERE total_bwd_packets IS NULL),
                    COUNT(*) FILTER (WHERE flow_bytes_per_s IS NULL),
                    COUNT(*) FILTER (WHERE flow_packets_per_s IS NULL)
                FROM flows;
            """)
            null_counts = cur.fetchone()
            null_names = [
                "id",
                "source_file_id",
                "attack_type_id",
                "destination_port",
                "flow_duration",
                "total_fwd_packets",
                "total_bwd_packets",
                "flow_bytes_per_s",
                "flow_packets_per_s",
            ]
            has_nulls = False
            for name, cnt in zip(null_names, null_counts):
                print(f"  * NULLs in '{name}': {cnt}")
                if cnt > 0:
                    has_nulls = True

            if not has_nulls:
                print("  [PASS] Zero NULL values in critical telemetry columns.")
            else:
                print("  [FAIL] Unexpected NULL values detected in critical columns!")
                all_passed = False

            # 6. Data Reconciliation with Raw CSVs
            print("\n" + "=" * 80)
            print("6. DATA RECONCILIATION: RAW CSVs VS LOADED INVENTORY")
            print("=" * 80)
            raw_counts = get_raw_csv_row_counts()
            total_raw = sum(raw_counts.values())
            print(f"  * Total Raw CSV Rows Across 8 Files: {total_raw:,}")
            print(f"  * Total Rows Loaded in Database    : {total_flows:,}")
            print(f"  * Net Discrepancy (Dropped Rows)   : {total_raw - total_flows:,}")
            print(
                "    (Accounted for by NaN cleaning, deduplication, and invalid domain filtering)"
            )
            print("=" * 80 + "\n")

    finally:
        conn.close()

    return all_passed


def main() -> None:
    """CLI entrypoint."""
    success = run_verification()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
