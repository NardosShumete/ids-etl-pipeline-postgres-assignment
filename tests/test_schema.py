"""Integration tests verifying PostgreSQL schema definitions, taxonomy seed, and idempotency."""

import pytest

from src.config import SQL_DIR


@pytest.fixture
def schema_sql() -> str:
    """Fixture returning the content of sql/01_schema.sql."""
    schema_path = SQL_DIR / "01_schema.sql"
    return schema_path.read_text(encoding="utf-8")


def test_schema_tables_and_primary_keys(schema_sql: str):
    """Verify all warehouse tables define explicit primary keys."""
    assert "CREATE TABLE attack_types" in schema_sql
    assert "id SMALLSERIAL PRIMARY KEY" in schema_sql

    assert "CREATE TABLE source_files" in schema_sql
    assert "id SERIAL PRIMARY KEY" in schema_sql

    assert "CREATE TABLE flows" in schema_sql
    assert "id BIGSERIAL PRIMARY KEY" in schema_sql

    assert "CREATE TABLE flow_statistics" in schema_sql
    assert (
        "flow_id BIGINT PRIMARY KEY REFERENCES flows(id) ON DELETE CASCADE"
        in schema_sql
    )


def test_schema_check_constraints(schema_sql: str):
    """Verify strict domain CHECK constraints on network attributes."""
    # Port range 0 - 65535
    assert "CHECK (destination_port >= 0 AND destination_port <= 65535)" in schema_sql
    # Non-negative durations and packet lengths
    assert "CHECK (flow_duration >= 0)" in schema_sql
    assert "CHECK (total_fwd_packets >= 0)" in schema_sql
    assert "CHECK (total_bwd_packets >= 0)" in schema_sql
    # Non-negative TCP flags
    assert "CHECK (fin_flag_count >= 0)" in schema_sql
    assert "CHECK (syn_flag_count >= 0)" in schema_sql
    assert "CHECK (ack_flag_count >= 0)" in schema_sql


def test_attack_types_seed_taxonomy(schema_sql: str):
    """Verify all 15 distinct intrusion categories are seeded into attack_types."""
    expected_categories = [
        "BENIGN",
        "DoS Hulk",
        "PortScan",
        "DDoS",
        "DoS GoldenEye",
        "FTP-Patator",
        "SSH-Patator",
        "DoS slowloris",
        "DoS Slowhttptest",
        "Bot",
        "Web Attack - Brute Force",
        "Web Attack - XSS",
        "Web Attack - Sql Injection",
        "Infiltration",
        "Heartbleed",
    ]
    for label in expected_categories:
        assert f"('{label}'" in schema_sql, f"Missing attack label in seed SQL: {label}"


def test_idempotency_file_check_logic():
    """(g) Test that is_file_already_loaded properly guards against re-inserting loaded files."""
    from unittest.mock import MagicMock

    from src.load import is_file_already_loaded

    # Mock connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Case 1: File has 0 rows (not loaded yet)
    mock_cursor.fetchone.return_value = (0,)
    assert not is_file_already_loaded(mock_conn, "test.csv")

    # Case 2: File has 200,000 rows (already loaded)
    mock_cursor.fetchone.return_value = (200_000,)
    assert is_file_already_loaded(mock_conn, "test.csv")

    # Case 3: File not in table
    mock_cursor.fetchone.return_value = None
    assert not is_file_already_loaded(mock_conn, "test.csv")
