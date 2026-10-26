"""Main Orchestration Pipeline for IDS ETL Process.

Provides the command-line interface and coordinates:
- Extraction and discovery of raw CSV files.
- Chunked ingestion and memory-efficient streaming.
- Cleaning, transformation, label standardization, and validation.
- Fast bulk loading via PostgreSQL `copy_expert`.
- Post-load index creation and query planner optimization.
- Comprehensive runtime metrics and audit reporting.

Usage:
    python -m src.pipeline
    python -m src.pipeline --limit 1000 --truncate
    python -m src.pipeline --chunk-size 100000
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Optional
import psycopg2
from tqdm import tqdm

from src.config import DEFAULT_CHUNK_SIZE, RAW_DATA_DIR, get_db_params
from src.extract import ensure_raw_data_extracted, read_csv_chunks
from src.load import (
    apply_post_load_indexes,
    get_attack_types_cache,
    get_or_create_source_file_id,
    is_file_already_loaded,
    load_chunk_to_postgres,
    run_analyze,
    truncate_tables,
)
from src.logger import setup_logger
from src.transform import TransformStats, transform_chunk

logger = setup_logger("pipeline")


def run_pipeline(
    limit: Optional[int] = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    truncate: bool = False,
    skip_indexes: bool = False,
    raw_dir: Path = RAW_DATA_DIR,
) -> TransformStats:
    """Execute the end-to-end ETL pipeline.

    Args:
        limit: Optional global maximum records to ingest (for sample testing).
        chunk_size: Number of records to process per batch.
        truncate: Whether to truncate data tables before loading.
        skip_indexes: Whether to skip post-load index creation.
        raw_dir: Directory containing raw CSV files.

    Returns:
        TransformStats: Cumulative statistics of the run.
    """
    start_time = time.time()
    logger.info("=" * 70)
    logger.info("STARTING IDS ETL PIPELINE (CIC-IDS-2017)")
    logger.info("Parameters: limit=%s, chunk_size=%d, truncate=%s, skip_indexes=%s", limit, chunk_size, truncate, skip_indexes)
    logger.info("=" * 70)

    # 1. Ensure raw CSV files are extracted
    csv_files = ensure_raw_data_extracted(target_dir=raw_dir)
    if not csv_files:
        logger.error("No CSV files found in %s.", raw_dir)
        sys.exit(1)

    logger.info("Found %d CSV file(s) to process.", len(csv_files))

    # 2. Connect to database
    db_params = get_db_params()
    conn = psycopg2.connect(**db_params)

    stats = TransformStats()

    try:
        # 3. Optional table truncation
        if truncate:
            truncate_tables(conn)

        # 4. Load attack type taxonomy mapping
        label_to_id = get_attack_types_cache(conn)

        total_processed_globally = 0

        # 5. Process each CSV file
        for file_idx, csv_file in enumerate(csv_files, 1):
            if limit is not None and total_processed_globally >= limit:
                logger.info("Reached global limit of %d rows. Stopping file ingestion.", limit)
                break

            logger.info(
                "[%d/%d] Processing file: %s (%.2f MB)",
                file_idx,
                len(csv_files),
                csv_file.name,
                csv_file.stat().st_size / 1024 / 1024,
            )

            # Check if file was already loaded
            if not truncate and is_file_already_loaded(conn, csv_file.name):
                logger.info("File '%s' already has loaded rows. Skipping (use --truncate to reload).", csv_file.name)
                continue

            source_file_id = get_or_create_source_file_id(conn, csv_file.name)

            # Determine remaining rows to read if limit is set
            file_limit = None
            if limit is not None:
                file_limit = limit - total_processed_globally

            # Read and process chunks
            chunk_generator = read_csv_chunks(
                file_path=csv_file,
                chunk_size=chunk_size,
                limit=file_limit,
            )

            with tqdm(desc=f"Loading {csv_file.name[:25]}", unit="chunk") as pbar:
                for chunk in chunk_generator:
                    flows_df, flow_stats_df = transform_chunk(
                        df=chunk,
                        label_to_id=label_to_id,
                        stats=stats,
                    )

                    if len(flows_df) > 0:
                        loaded = load_chunk_to_postgres(
                            conn=conn,
                            flows_df=flows_df,
                            flow_stats_df=flow_stats_df,
                            source_file_id=source_file_id,
                        )
                        total_processed_globally += loaded

                    pbar.update(1)

                    if limit is not None and total_processed_globally >= limit:
                        break

        # 6. Apply post-load indexes and analyze
        if not skip_indexes and stats.rows_loaded > 0:
            logger.info("Ingestion completed. Creating post-load database indexes...")
            apply_post_load_indexes(conn)
            run_analyze(conn)
        elif skip_indexes:
            logger.info("Skipping post-load indexes as requested (--skip-indexes).")

        # 7. Query database counts for verification
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM flows;")
            db_flows_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM flow_statistics;")
            db_stats_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM source_files WHERE row_count > 0;")
            db_files_count = cur.fetchone()[0]

    finally:
        conn.close()

    elapsed = time.time() - start_time
    minutes, seconds = divmod(elapsed, 60)

    # 8. Final Execution Summary Report
    print("\n" + "=" * 75)
    print("                      ETL PIPELINE EXECUTION SUMMARY")
    print("=" * 75)
    print(f"Total Elapsed Time           : {int(minutes)}m {seconds:.2f}s")
    print(f"Total Rows Read From CSVs    : {stats.rows_read:,}")
    print(f"Total Rows Dropped           : {stats.total_dropped():,}")
    print(f"  - Dropped Duplicates       : {stats.rows_dropped_duplicates:,}")
    print(f"  - Dropped Missing (NaN)    : {stats.rows_dropped_nan:,}")
    print(f"  - Dropped Invalid/Negative : {stats.rows_dropped_invalid:,}")
    print(f"Total Rows Successfully Loaded: {stats.rows_loaded:,}")
    print("-" * 75)
    print("DATABASE VERIFICATION:")
    print(f"  - flows table count        : {db_flows_count:,}")
    print(f"  - flow_statistics count    : {db_stats_count:,}")
    print(f"  - Active source files      : {db_files_count:,}")
    print("=" * 75 + "\n")

    logger.info("Pipeline execution finished successfully.")
    return stats


def main() -> None:
    """Parse CLI arguments and run pipeline."""
    parser = argparse.ArgumentParser(
        description="Run the CIC-IDS-2017 ETL Ingestion Pipeline into PostgreSQL.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only a sample of up to N records across files (useful for testing).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Number of records per chunk (default: {DEFAULT_CHUNK_SIZE}).",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate database tables before loading to perform a fresh re-run.",
    )
    parser.add_argument(
        "--skip-indexes",
        action="store_true",
        help="Skip post-load index creation (recommended during rapid sample testing).",
    )

    args = parser.parse_args()

    try:
        run_pipeline(
            limit=args.limit,
            chunk_size=args.chunk_size,
            truncate=args.truncate,
            skip_indexes=args.skip_indexes,
        )
    except Exception as err:
        logger.critical("Pipeline aborted due to unexpected error: %s", err, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
