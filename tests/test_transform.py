"""Unit and integration tests for data transformation and cleaning logic."""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.config import RAW_DATA_DIR
from src.transform import (
    FLOWS_COLUMNS,
    FLOW_STATS_COLUMNS,
    TransformStats,
    clean_attack_label,
    clean_column_name,
    transform_chunk,
)


@pytest.fixture
def mock_label_to_id():
    """Sample taxonomy mapping mirroring seeded PostgreSQL attack_types."""
    return {
        "BENIGN": 1,
        "DoS Hulk": 2,
        "PortScan": 3,
        "DDoS": 4,
        "DoS GoldenEye": 5,
        "FTP-Patator": 6,
        "SSH-Patator": 7,
        "DoS slowloris": 8,
        "DoS Slowhttptest": 9,
        "Bot": 10,
        "Web Attack - Brute Force": 11,
        "Web Attack - XSS": 12,
        "Web Attack - Sql Injection": 13,
        "Infiltration": 14,
        "Heartbleed": 15,
    }


def test_clean_column_name():
    """Verify column normalization rules."""
    assert clean_column_name(" Destination Port") == "destination_port"
    assert clean_column_name(" Flow Duration") == "flow_duration"
    assert clean_column_name("Total Backward Packets") == "total_bwd_packets"
    assert clean_column_name("Flow Bytes/s") == "flow_bytes_per_s"
    assert clean_column_name("Down/Up Ratio") == "down_up_ratio"
    assert clean_column_name(" Fwd Header Length.1") == "fwd_header_length_1"


def test_clean_attack_label():
    """Verify normalization of non-standard dash characters and typos in labels."""
    assert clean_attack_label("BENIGN") == "BENIGN"
    assert clean_attack_label("Web Attack \ufffd Brute Force") == "Web Attack - Brute Force"
    assert clean_attack_label("Web Attack \x96 XSS") == "Web Attack - XSS"
    assert clean_attack_label("Web Attack  Sql Injection") == "Web Attack - Sql Injection"
    assert clean_attack_label("Infilteration") == "Infiltration"
    assert clean_attack_label("DoS Hulk") == "DoS Hulk"


def test_transform_chunk_synthetic(mock_label_to_id):
    """Test cleaning rules on synthetic records with known defects."""
    raw_data = {
        " Destination Port": [80, 443, -1, 8080, 80],
        " Flow Duration": [1000, 2000, 3000, -50, 1000],  # row 3 has negative duration, row 4 duplicate of row 0
        " Total Fwd Packets": [10, 20, 10, 5, 10],
        " Total Backward Packets": [5, 10, 5, 2, 5],
        "Total Length of Fwd Packets": [100, 200, 100, 50, 100],
        " Total Length of Bwd Packets": [50, 100, 50, 25, 50],
        "Flow Bytes/s": [100.0, np.inf, 50.0, 10.0, 100.0],  # row 1 has inf -> dropped
        " Flow Packets/s": [15.0, 30.0, 15.0, 7.0, 15.0],
        " Fwd Header Length": [20, 40, 20, 10, 20],
        " Fwd Header Length.1": [20, 40, 20, 10, 20],  # duplicate column
        " Label": [
            "BENIGN",
            "Web Attack \ufffd Brute Force",
            "BENIGN",
            "BENIGN",
            "BENIGN",  # row 4 is duplicate of row 0
        ],
    }
    df = pd.DataFrame(raw_data)
    stats = TransformStats()

    flows_df, stats_df = transform_chunk(df, mock_label_to_id, stats)

    # Row 1 (inf) dropped, Row 2 (negative port) dropped, Row 3 (negative duration) dropped,
    # Row 4 (duplicate of Row 0) dropped
    assert len(flows_df) == 1
    assert len(stats_df) == 1
    assert "fwd_header_length_1" not in flows_df.columns
    assert "fwd_header_length_1" not in stats_df.columns
    assert flows_df.iloc[0]["destination_port"] == 80
    assert flows_df.iloc[0]["attack_type_id"] == 1  # BENIGN


def test_transform_chunk_on_real_1000_sample(mock_label_to_id):
    """Test transform_chunk against a real 1,000 row slice from the dataset."""
    sample_files = list(RAW_DATA_DIR.glob("*.csv"))
    if not sample_files:
        pytest.skip("No CSV files found in data/raw for integration testing.")

    test_file = sample_files[0]
    raw_df = pd.read_csv(test_file, nrows=1000, encoding="latin-1", low_memory=False)
    raw_df["_source_file_name"] = test_file.name

    stats = TransformStats()
    flows_df, flow_stats_df = transform_chunk(raw_df, mock_label_to_id, stats)

    # Verify rows were processed
    assert stats.rows_read == 1000
    assert len(flows_df) > 0
    assert len(flows_df) == len(flow_stats_df)

    # Verify column structures
    for col in ["destination_port", "flow_duration", "total_fwd_packets", "attack_type_id"]:
        assert col in flows_df.columns

    # Verify domain boundaries on output
    assert (flows_df["destination_port"] >= 0).all()
    assert (flows_df["destination_port"] <= 65535).all()
    assert (flows_df["flow_duration"] >= 0).all()
    assert (flows_df["attack_type_id"] > 0).all()

    # Verify no infinite or NaN values in core metrics
    assert not flows_df["flow_bytes_per_s"].isna().any()
    assert not np.isinf(flows_df["flow_bytes_per_s"]).any()
