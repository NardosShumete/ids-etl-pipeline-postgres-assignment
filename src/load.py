"""Database Loading Module for IDS ETL Pipeline.

Implements high-performance bulk loading into PostgreSQL using `copy_expert`
via in-memory StringIO buffers, transaction management, foreign key synchronization,
and post-load index maintenance.
"""

import io
from pathlib import Path
from typing import Dict, Optional
import pandas as pd
import psycopg2
from psycopg2.extensions import connection as PgConnection

from src.config import SQL_DIR
from src.logger import setup_logger

logger = setup_logger("load")


def get_attack_types_cache(conn: PgConnection) -> Dict[str, int]:
    """Fetch current attack_types taxonomy from PostgreSQL as a label->id mapping."""
    with conn.cursor() as cur:
        cur.execute("SELECT label, id FROM attack_types;")
        rows = cur.fetchall()
    cache = {label: id_ for label, id_ in rows}
    logger.info("Loaded %d attack types from database cache.", len(cache))
    return cache


def extract_capture_day(file_name: str) -> str:
    """Infer capture weekday from CSV filename.

    Example:
        'Monday-WorkingHours.pcap_ISCX.csv' -> 'Monday'
    """
    first_part = file_name.split("-")[0].capitalize()
    valid_days = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}
    return first_part if first_part in valid_days else "Unknown"


def get_or_create_source_file_id(conn: PgConnection, file_name: str) -> int:
    """Retrieve or insert source file audit entry, returning its surrogate primary key."""
    capture_day = extract_capture_day(file_name)
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM source_files WHERE file_name = %s;", (file_name,))
        row = cur.fetchone()
        if row:
            return row[0]

        cur.execute(
            """
            INSERT INTO source_files (file_name, capture_day, row_count)
            VALUES (%s, %s, 0)
            RETURNING id;
            """,
            (file_name, capture_day),
        )
        file_id = cur.fetchone()[0]
    conn.commit()
    logger.info("Registered source file '%s' (Day: %s) with id=%d", file_name, capture_day, file_id)
    return file_id


def is_file_already_loaded(conn: PgConnection, file_name: str) -> bool:
    """Check if the source file has already been ingested with records."""
    with conn.cursor() as cur:
        cur.execute("SELECT row_count FROM source_files WHERE file_name = %s;", (file_name,))
        row = cur.fetchone()
        if row and row[0] > 0:
            return True
    return False


def truncate_tables(conn: PgConnection) -> None:
    """Truncate data tables and reset primary key sequences for clean re-runs."""
    logger.info("Truncating flows, flow_statistics, and source_files tables...")
    with conn.cursor() as cur:
        cur.execute("TRUNCATE flow_statistics, flows, source_files RESTART IDENTITY CASCADE;")
    conn.commit()
    logger.info("Tables truncated and sequences reset.")


def load_chunk_to_postgres(
    conn: PgConnection,
    flows_df: pd.DataFrame,
    flow_stats_df: pd.DataFrame,
    source_file_id: int,
) -> int:
    """Bulk-load a chunk into PostgreSQL `flows` and `flow_statistics` tables.

    Uses `copy_expert` with in-memory CSV buffers for fast streaming while
    synchronizing the 1:1 surrogate primary/foreign key `flows.id = flow_statistics.flow_id`.

    Args:
        conn: Open psycopg2 database connection.
        flows_df: Cleaned core telemetry DataFrame.
        flow_stats_df: Cleaned statistical distribution DataFrame.
        source_file_id: Foreign key reference to `source_files.id`.

    Returns:
        int: Number of records successfully inserted.
    """
    row_count = len(flows_df)
    if row_count == 0:
        return 0

    try:
        with conn.cursor() as cur:
            # 1. Reserve surrogate IDs from flows_id_seq for this entire chunk
            cur.execute("SELECT nextval('flows_id_seq');")
            start_id = cur.fetchone()[0]
            end_id = start_id + row_count - 1
            cur.execute("SELECT setval('flows_id_seq', %s, true);", (end_id,))

            assigned_ids = list(range(start_id, start_id + row_count))

            # 2. Attach IDs and FKs to DataFrames
            flows_df_copy = flows_df.copy()
            flows_df_copy["id"] = assigned_ids
            flows_df_copy["source_file_id"] = source_file_id

            # Remove any internal temporary lineage columns
            if "_source_file_name" in flows_df_copy.columns:
                flows_df_copy.drop(columns=["_source_file_name"], inplace=True)

            flow_stats_copy = flow_stats_df.copy()
            flow_stats_copy["flow_id"] = assigned_ids

            # 3. Stream `flows` table via COPY
            flows_buffer = io.StringIO()
            flows_df_copy.to_csv(flows_buffer, index=False)
            flows_buffer.seek(0)
            flows_columns_str = ", ".join(flows_df_copy.columns)
            cur.copy_expert(
                f"COPY flows ({flows_columns_str}) FROM STDIN WITH CSV HEADER NULL ''",
                flows_buffer,
            )

            # 4. Stream `flow_statistics` table via COPY
            stats_buffer = io.StringIO()
            flow_stats_copy.to_csv(stats_buffer, index=False)
            stats_buffer.seek(0)
            stats_columns_str = ", ".join(flow_stats_copy.columns)
            cur.copy_expert(
                f"COPY flow_statistics ({stats_columns_str}) FROM STDIN WITH CSV HEADER NULL ''",
                stats_buffer,
            )

            # 5. Update ingested row count on source_files
            cur.execute(
                "UPDATE source_files SET row_count = row_count + %s WHERE id = %s;",
                (row_count, source_file_id),
            )

        # Commit transaction for this chunk
        conn.commit()
        return row_count

    except Exception as err:
        conn.rollback()
        logger.error("Failed to load chunk into PostgreSQL: %s", err)
        raise


def apply_post_load_indexes(conn: PgConnection, index_file: Optional[Path] = None) -> None:
    """Execute SQL index creation script against database."""
    if index_file is None:
        index_file = SQL_DIR / "02_indexes.sql"

    logger.info("Applying post-load performance indexes from %s...", index_file.name)
    with open(index_file, "r", encoding="utf-8") as f:
        index_sql = f.read()

    with conn.cursor() as cur:
        cur.execute(index_sql)
    conn.commit()
    logger.info("Post-load indexes created successfully.")


def run_analyze(conn: PgConnection) -> None:
    """Run ANALYZE to update PostgreSQL query planner statistics."""
    logger.info("Running PostgreSQL ANALYZE to update query planner statistics...")
    old_isolation = conn.isolation_level
    try:
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cur:
            cur.execute("ANALYZE;")
        logger.info("ANALYZE completed successfully.")
    finally:
        conn.set_isolation_level(old_isolation)
