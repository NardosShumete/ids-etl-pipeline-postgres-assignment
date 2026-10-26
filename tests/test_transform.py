"""Unit and integration tests for data transformation and cleaning logic."""

import numpy as np
import pandas as pd
import pytest

from src.config import RAW_DATA_DIR
from src.transform import (
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


def test_clean_attack_label_corrupted_encodings():
    """Verify label cleaning of the 3 Web Attack classes with corrupted encodings and anomalies."""
    # 1. Web Attack - Brute Force with unicode replacement character U+FFFD (\ufffd)
    assert (
        clean_attack_label("Web Attack \ufffd Brute Force")
        == "Web Attack - Brute Force"
    )
    # 2. Web Attack - XSS with Windows-1252 / Latin-1 en-dash byte \x96
    assert clean_attack_label("Web Attack \x96 XSS") == "Web Attack - XSS"
    # 3. Web Attack - Sql Injection with corrupted double-space gap
    assert (
        clean_attack_label("Web Attack  Sql Injection") == "Web Attack - Sql Injection"
    )
    # Other anomalies
    assert clean_attack_label("Infilteration") == "Infiltration"
    assert clean_attack_label("  BENIGN  ") == "BENIGN"
    assert clean_attack_label("DoS Hulk") == "DoS Hulk"


def test_deduplicate_chunk(mock_label_to_id):
    """(a) Test duplicate removal and verify stats counting on identical records."""
    raw_data = {
        " Destination Port": [80, 80, 443],
        " Flow Duration": [1000, 1000, 2000],
        " Total Fwd Packets": [10, 10, 20],
        " Total Backward Packets": [5, 5, 10],
        "Total Length of Fwd Packets": [100, 100, 200],
        " Total Length of Bwd Packets": [50, 50, 100],
        "Flow Bytes/s": [100.0, 100.0, 150.0],
        " Flow Packets/s": [15.0, 15.0, 30.0],
        " Fwd Header Length": [20, 20, 40],
        " Label": ["BENIGN", "BENIGN", "BENIGN"],
    }
    df = pd.DataFrame(raw_data)
    stats = TransformStats()

    flows_df, stats_df = transform_chunk(df, mock_label_to_id, stats)

    # First two rows are identical; second row must be dropped
    assert len(flows_df) == 2
    assert len(stats_df) == 2
    assert stats.rows_dropped_duplicates == 1


def test_infinity_and_nan_dropped(mock_label_to_id):
    """(b) Test that Infinity and NaN values in crucial columns are dropped and counted."""
    raw_data = {
        " Destination Port": [80, 80, 80],
        " Flow Duration": [1000, 2000, 3000],
        " Total Fwd Packets": [10, 20, 30],
        " Total Backward Packets": [5, 10, 15],
        "Total Length of Fwd Packets": [100, 200, 300],
        " Total Length of Bwd Packets": [50, 100, 150],
        "Flow Bytes/s": [100.0, np.inf, np.nan],  # rows 1 and 2 must be dropped
        " Flow Packets/s": [15.0, 30.0, 45.0],
        " Fwd Header Length": [20, 40, 60],
        " Label": ["BENIGN", "BENIGN", "BENIGN"],
    }
    df = pd.DataFrame(raw_data)
    stats = TransformStats()

    flows_df, stats_df = transform_chunk(df, mock_label_to_id, stats)

    assert len(flows_df) == 1
    assert len(stats_df) == 1
    assert stats.rows_dropped_nan == 2


def test_negative_flow_duration_dropped(mock_label_to_id):
    """(c) Test that negative flow_duration rows (clock jitter) are filtered out."""
    raw_data = {
        " Destination Port": [80, 443, 8080],
        " Flow Duration": [1000, -1, -500],  # rows 1 and 2 negative duration
        " Total Fwd Packets": [10, 20, 30],
        " Total Backward Packets": [5, 10, 15],
        "Total Length of Fwd Packets": [100, 200, 300],
        " Total Length of Bwd Packets": [50, 100, 150],
        "Flow Bytes/s": [100.0, 200.0, 300.0],
        " Flow Packets/s": [15.0, 30.0, 45.0],
        " Fwd Header Length": [20, 40, 60],
        " Label": ["BENIGN", "BENIGN", "BENIGN"],
    }
    df = pd.DataFrame(raw_data)
    stats = TransformStats()

    flows_df, stats_df = transform_chunk(df, mock_label_to_id, stats)

    assert len(flows_df) == 1
    assert len(stats_df) == 1
    assert stats.rows_dropped_invalid == 2
    assert flows_df.iloc[0]["flow_duration"] == 1000


def test_vertical_split_matching_rows_and_features(mock_label_to_id):
    """(f) Verify vertical partitioning generates synchronized DataFrames with distinct feature sets."""
    sample_files = list(RAW_DATA_DIR.glob("*.csv"))
    if not sample_files:
        pytest.skip("No CSV files found in data/raw for integration testing.")

    test_file = sample_files[0]
    raw_df = pd.read_csv(test_file, nrows=500, encoding="latin-1", low_memory=False)

    stats = TransformStats()
    flows_df, flow_stats_df = transform_chunk(raw_df, mock_label_to_id, stats)

    # 1. Must produce exact equal cardinality
    assert len(flows_df) == len(flow_stats_df)
    assert len(flows_df) > 0

    # 2. flows table must contain core hot features
    assert "destination_port" in flows_df.columns
    assert "flow_duration" in flows_df.columns
    assert "attack_type_id" in flows_df.columns

    # 3. flow_statistics table must contain forensic and variance metrics
    assert "fwd_packet_length_max" in flow_stats_df.columns
    assert "packet_length_mean" in flow_stats_df.columns

    # 4. No overlap between partitioned telemetry and variance features
    assert "fwd_packet_length_max" not in flows_df.columns
    assert "attack_type_id" not in flow_stats_df.columns
