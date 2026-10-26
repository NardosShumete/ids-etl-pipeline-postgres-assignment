"""Unit tests verifying DDL schema definitions, constraints, and index scripts."""

from pathlib import Path
import pytest


@pytest.fixture
def project_root() -> Path:
    """Fixture returning the root directory of the repository."""
    return Path(__file__).resolve().parent.parent


def test_schema_file_exists(project_root: Path) -> None:
    """Verify that sql/01_schema.sql exists and contains valid table definitions."""
    schema_file = project_root / "sql" / "01_schema.sql"
    assert schema_file.is_file(), "sql/01_schema.sql does not exist"

    content = schema_file.read_text(encoding="utf-8")
    assert len(content) > 100, "sql/01_schema.sql is suspiciously empty"

    # Verify all four required core tables are created
    assert "CREATE TABLE attack_types" in content
    assert "CREATE TABLE source_files" in content
    assert "CREATE TABLE flows" in content
    assert "CREATE TABLE flow_statistics" in content

    # Verify essential constraints and references
    assert "REFERENCES source_files(id)" in content
    assert "REFERENCES attack_types(id)" in content
    assert "REFERENCES flows(id)" in content
    assert "CHECK (destination_port >= 0 AND destination_port <= 65535)" in content
    assert "CHECK (flow_duration >= 0)" in content


def test_attack_types_seeded(project_root: Path) -> None:
    """Verify that seed statements populate core attack categories."""
    schema_file = project_root / "sql" / "01_schema.sql"
    content = schema_file.read_text(encoding="utf-8")

    expected_labels = [
        "BENIGN",
        "DoS Hulk",
        "PortScan",
        "DDoS",
        "FTP-Patator",
        "SSH-Patator",
        "Bot",
        "Infiltration",
        "Heartbleed",
    ]

    for label in expected_labels:
        assert label in content, f"Expected attack label '{label}' not found in seed SQL"


def test_indexes_file_exists(project_root: Path) -> None:
    """Verify that sql/02_indexes.sql exists and defines required post-load indexes."""
    indexes_file = project_root / "sql" / "02_indexes.sql"
    assert indexes_file.is_file(), "sql/02_indexes.sql does not exist"

    content = indexes_file.read_text(encoding="utf-8")
    assert "idx_flows_attack_type_id" in content
    assert "idx_flows_destination_port" in content
    assert "idx_flows_source_file_id" in content
