"""Data Cleaning and Transformation Module for IDS ETL Pipeline.

Cleans and standardizes raw CIC-IDS-2017 network flow chunks:
- Normalizes column names to snake_case and removes duplicate headers.
- Converts infinite and invalid values to NaN, handling missing values gracefully.
- Deduplicates flow records.
- Standardizes attack labels (handling non-standard dash encodings) and maps to attack_type_id.
- Validates domain boundaries and non-negative constraints.
- Vertically partitions records into `flows` and `flow_statistics` DataFrames.
"""

import re

import numpy as np
import pandas as pd

from src.logger import setup_logger

logger = setup_logger("transform")

# Mapping from sanitized raw column names to canonical PostgreSQL column names
RAW_TO_DB_MAP: dict[str, str] = {
    "total_backward_packets": "total_bwd_packets",
    "fwd_avg_bytes_per_bulk": "fwd_avg_bytes_bulk",
    "fwd_avg_packets_per_bulk": "fwd_avg_packets_bulk",
    "bwd_avg_bytes_per_bulk": "bwd_avg_bytes_bulk",
    "bwd_avg_packets_per_bulk": "bwd_avg_packets_bulk",
    "down_per_up_ratio": "down_up_ratio",
    "fwd_pkts_per_s": "fwd_packets_per_s",
    "bwd_pkts_per_s": "bwd_packets_per_s",
}

# Core columns belonging to the `flows` table
FLOWS_COLUMNS: list[str] = [
    "destination_port",
    "flow_duration",
    "total_fwd_packets",
    "total_bwd_packets",
    "total_length_of_fwd_packets",
    "total_length_of_bwd_packets",
    "flow_bytes_per_s",
    "flow_packets_per_s",
    "flow_iat_mean",
    "flow_iat_std",
    "flow_iat_max",
    "flow_iat_min",
    "fin_flag_count",
    "syn_flag_count",
    "rst_flag_count",
    "psh_flag_count",
    "ack_flag_count",
    "urg_flag_count",
    "cwe_flag_count",
    "ece_flag_count",
    "down_up_ratio",
    "average_packet_size",
]

# Statistical columns belonging to the `flow_statistics` table
FLOW_STATS_COLUMNS: list[str] = [
    "fwd_packet_length_max",
    "fwd_packet_length_min",
    "fwd_packet_length_mean",
    "fwd_packet_length_std",
    "bwd_packet_length_max",
    "bwd_packet_length_min",
    "bwd_packet_length_mean",
    "bwd_packet_length_std",
    "min_packet_length",
    "max_packet_length",
    "packet_length_mean",
    "packet_length_std",
    "packet_length_variance",
    "fwd_iat_total",
    "fwd_iat_mean",
    "fwd_iat_std",
    "fwd_iat_max",
    "fwd_iat_min",
    "bwd_iat_total",
    "bwd_iat_mean",
    "bwd_iat_std",
    "bwd_iat_max",
    "bwd_iat_min",
    "fwd_psh_flags",
    "bwd_psh_flags",
    "fwd_urg_flags",
    "bwd_urg_flags",
    "fwd_header_length",
    "bwd_header_length",
    "fwd_packets_per_s",
    "bwd_packets_per_s",
    "avg_fwd_segment_size",
    "avg_bwd_segment_size",
    "fwd_avg_bytes_bulk",
    "fwd_avg_packets_bulk",
    "fwd_avg_bulk_rate",
    "bwd_avg_bytes_bulk",
    "bwd_avg_packets_bulk",
    "bwd_avg_bulk_rate",
    "subflow_fwd_packets",
    "subflow_fwd_bytes",
    "subflow_bwd_packets",
    "subflow_bwd_bytes",
    "init_win_bytes_forward",
    "init_win_bytes_backward",
    "act_data_pkt_fwd",
    "min_seg_size_forward",
    "active_mean",
    "active_std",
    "active_max",
    "active_min",
    "idle_mean",
    "idle_std",
    "idle_max",
    "idle_min",
]


def clean_column_name(raw_name: str) -> str:
    """Standardize column names to clean lowercase snake_case.

    Examples:
        ' Destination Port' -> 'destination_port'
        'Flow Bytes/s' -> 'flow_bytes_per_s'
        ' Fwd Header Length.1' -> 'fwd_header_length_1'
    """
    col = raw_name.strip()
    col = col.replace("/", "_per_")
    col = re.sub(r"[^a-zA-Z0-9_]", "_", col)
    col = re.sub(r"_+", "_", col)
    col = col.lower().strip("_")
    return RAW_TO_DB_MAP.get(col, col)


def clean_attack_label(label: str) -> str:
    """Normalize attack label strings and fix encoding/dash variations.

    Examples:
        'Web Attack \ufffd Brute Force' -> 'Web Attack - Brute Force'
        'Web Attack  XSS' -> 'Web Attack - XSS'
        'Infilteration' -> 'Infiltration'
    """
    if not isinstance(label, str):
        return "BENIGN"

    label = label.strip()

    # Normalize Web Attack hyphenation variations (including replacement char \ufffd, en-dash \x96)
    if "web attack" in label.lower():
        label = re.sub(
            r"Web Attack[\s\uFFFD\u0096\u2013\u2014\-]+", "Web Attack - ", label
        )
        # Normalize specific sub-labels
        if "brute" in label.lower():
            return "Web Attack - Brute Force"
        if "xss" in label.lower():
            return "Web Attack - XSS"
        if "sql" in label.lower():
            return "Web Attack - Sql Injection"

    # Normalize spelling variations
    if label.lower() == "infilteration":
        return "Infiltration"

    # Collapse any extraneous internal whitespace
    label = re.sub(r"\s+", " ", label).strip()
    return label


class TransformStats:
    """Tracks rows processed, dropped, and reasons for summary reporting."""

    def __init__(self) -> None:
        self.rows_read: int = 0
        self.rows_dropped_duplicates: int = 0
        self.rows_dropped_nan: int = 0
        self.rows_dropped_invalid: int = 0
        self.rows_loaded: int = 0

    def total_dropped(self) -> int:
        return (
            self.rows_dropped_duplicates
            + self.rows_dropped_nan
            + self.rows_dropped_invalid
        )


def transform_chunk(
    df: pd.DataFrame,
    label_to_id: dict[str, int],
    stats: TransformStats | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Clean and transform a single DataFrame chunk.

    Args:
        df: Raw DataFrame chunk from CSV.
        label_to_id: Dictionary mapping attack label to attack_type_id integer.
        stats: Optional stats accumulator for reporting.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: Cleaned (flows_df, flow_stats_df).
    """
    if stats is None:
        stats = TransformStats()

    initial_count = len(df)
    stats.rows_read += initial_count

    # 1. Clean column headers
    df.columns = [clean_column_name(c) for c in df.columns]

    # 2. Drop duplicate 'fwd_header_length' column if present
    # In raw CSVs, column 56 is 'Fwd Header Length.1' (cleaned to 'fwd_header_length_1')
    if "fwd_header_length_1" in df.columns:
        df.drop(columns=["fwd_header_length_1"], inplace=True)

    # 3. Replace Infinity / -Infinity with NaN across numeric features
    df.replace([np.inf, -np.inf], np.nan, inplace=True)

    # 4. Handle NaN: Drop rows missing crucial connection metrics
    crucial_cols = [
        "destination_port",
        "flow_duration",
        "flow_bytes_per_s",
        "flow_packets_per_s",
        "label",
    ]
    crucial_existing = [c for c in crucial_cols if c in df.columns]
    nan_mask = df[crucial_existing].isna().any(axis=1)
    nan_count = int(nan_mask.sum())
    if nan_count > 0:
        stats.rows_dropped_nan += nan_count
        df = df.loc[~nan_mask].copy()

    # 5. Drop duplicate rows based on flow telemetry
    feature_cols = [c for c in df.columns if not c.startswith("_")]
    before_dedup = len(df)
    df.drop_duplicates(subset=feature_cols, inplace=True)
    dedup_dropped = before_dedup - len(df)
    stats.rows_dropped_duplicates += dedup_dropped

    # 6. Clean attack labels and map to attack_type_id
    if "label" in df.columns:
        df["cleaned_label"] = df["label"].astype(str).apply(clean_attack_label)
        df["attack_type_id"] = df["cleaned_label"].map(label_to_id)
        if df["attack_type_id"].isna().any():
            unmapped = sorted(
                df.loc[df["attack_type_id"].isna(), "cleaned_label"].unique()
            )
            logger.error(
                "Unmapped attack labels found: %s. "
                "Update attack_types before loading the data.",
                unmapped,
            )
            raise ValueError(
                "Unmapped attack labels found: "
                + ", ".join(repr(label) for label in unmapped)
            )
        df["attack_type_id"] = df["attack_type_id"].astype("int16")

    # 7. Validate non-negative domain rules
    # Drop rows where ports or durations or packet totals are negative
    invalid_mask = (
        (df["destination_port"] < 0)
        | (df["destination_port"] > 65535)
        | (df["flow_duration"] < 0)
        | (df["total_fwd_packets"] < 0)
        | (df["total_bwd_packets"] < 0)
        | (df["total_length_of_fwd_packets"] < 0)
        | (df["total_length_of_bwd_packets"] < 0)
    )
    invalid_count = int(invalid_mask.sum())
    if invalid_count > 0:
        stats.rows_dropped_invalid += invalid_count
        df = df.loc[~invalid_mask].copy()

    # Clip minor microsecond timing jitter (e.g. -12 microseconds) to 0 for non-negative check constraints
    non_neg_stat_cols = [
        "fwd_iat_min",
        "bwd_iat_min",
        "flow_iat_min",
        "packet_length_variance",
        "active_min",
        "idle_min",
    ]
    for col in non_neg_stat_cols:
        if col in df.columns:
            df[col] = df[col].clip(lower=0)

    # 8. Downcast numeric data types to match PostgreSQL schema
    int_cols_32 = ["destination_port"]
    int_cols_64 = [
        "flow_duration",
        "total_fwd_packets",
        "total_bwd_packets",
        "total_length_of_fwd_packets",
        "total_length_of_bwd_packets",
    ]
    flag_cols = [c for c in df.columns if "flag" in c]

    for col in int_cols_32:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype("int32")
    for col in int_cols_64:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype("int64")
    for col in flag_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype("int16")

    # Fill remaining NaNs in statistics with 0.0
    for col in FLOW_STATS_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # 9. Vertically partition into flows and flow_statistics DataFrames
    flows_selected = [c for c in FLOWS_COLUMNS if c in df.columns]
    flows_df = df[flows_selected].copy()
    flows_df["attack_type_id"] = df["attack_type_id"]
    if "_source_file_name" in df.columns:
        flows_df["_source_file_name"] = df["_source_file_name"]

    stats_selected = [c for c in FLOW_STATS_COLUMNS if c in df.columns]
    flow_stats_df = df[stats_selected].copy()

    stats.rows_loaded += len(flows_df)

    return flows_df, flow_stats_df
