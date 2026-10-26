"""Data Extraction Module for IDS ETL Pipeline.

Handles unzipping archive files, discovering CSV datasets (including resolving
nested subfolder layouts), reading files in memory-efficient chunks, and handling
encoding fallbacks.
"""

import shutil
import zipfile
from collections.abc import Generator
from pathlib import Path

import pandas as pd

from src.config import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_ZIP_PATH,
    FALLBACK_ENCODINGS,
    RAW_DATA_DIR,
)
from src.logger import setup_logger

logger = setup_logger("extract")


def ensure_raw_data_extracted(
    zip_path: Path = DEFAULT_ZIP_PATH,
    target_dir: Path = RAW_DATA_DIR,
) -> list[Path]:
    """Ensure CSV files are extracted and available in target directory.

    If CSV files are already present in target_dir, extraction is skipped.
    If CSVs were zipped inside a subfolder, they are automatically flattened
    into target_dir.

    Args:
        zip_path: Path to the archive.zip file.
        target_dir: Destination directory for raw CSV files (e.g. data/raw).

    Returns:
        List[Path]: Sorted list of absolute paths to extracted CSV files.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    existing_csvs = list(target_dir.glob("*.csv"))

    if existing_csvs:
        logger.info(
            "Found %d existing CSV file(s) in %s. Skipping extraction.",
            len(existing_csvs),
            target_dir,
        )
        return sorted(existing_csvs)

    # Check for nested CSVs in subdirectories of target_dir
    nested_csvs = list(target_dir.glob("*/**/*.csv"))
    if nested_csvs:
        logger.info(
            "Found %d nested CSV file(s). Flattening into %s...",
            len(nested_csvs),
            target_dir,
        )
        for nested in nested_csvs:
            destination = target_dir / nested.name
            if nested != destination:
                shutil.move(str(nested), str(destination))
        # Clean up empty nested directories
        for item in target_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
        return sorted(target_dir.glob("*.csv"))

    # Verify archive.zip exists
    if not zip_path.is_file():
        # Fallback check for any .zip file in zip_path.parent
        zip_candidates = list(zip_path.parent.glob("*.zip"))
        if zip_candidates:
            zip_path = zip_candidates[0]
            logger.info("Using discovered archive file: %s", zip_path)
        else:
            raise FileNotFoundError(
                f"Dataset archive not found at {zip_path}. Please place archive.zip in data/."
            )

    logger.info("Extracting %s into %s...", zip_path.name, target_dir)
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(path=target_dir)

    # Flatten any subfolders created by extraction (e.g. MachineLearningCSV/)
    extracted_csvs = list(target_dir.rglob("*.csv"))
    if not extracted_csvs:
        raise RuntimeError(
            f"Extraction completed but no .csv files found in {target_dir}"
        )

    for csv_file in extracted_csvs:
        destination = target_dir / csv_file.name
        if csv_file.resolve() != destination.resolve():
            shutil.move(str(csv_file), str(destination))

    # Remove lingering subdirectories
    for item in target_dir.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)

    final_csvs = sorted(target_dir.glob("*.csv"))
    logger.info(
        "Extraction complete. %d CSV file(s) ready in %s.", len(final_csvs), target_dir
    )
    return final_csvs


def get_raw_csv_files(raw_dir: Path = RAW_DATA_DIR) -> list[Path]:
    """Return all CSV file paths in the raw data directory."""
    return sorted(raw_dir.glob("*.csv"))


def read_csv_chunks(
    file_path: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    limit: int | None = None,
) -> Generator[pd.DataFrame, None, None]:
    """Read a CSV file in chunks with encoding fallback and file lineage metadata.

    Args:
        file_path: Path to the CSV file.
        chunk_size: Number of records per chunk.
        limit: Maximum total rows to yield from this file (useful for testing).

    Yields:
        pd.DataFrame: Chunks of raw network flow records with '_source_file_name' attached.
    """
    total_yielded = 0
    selected_encoding = None

    for encoding in FALLBACK_ENCODINGS:
        try:
            # Test encoding on the header
            with open(file_path, "r", encoding=encoding) as f:
                f.readline()
            selected_encoding = encoding
            break
        except (UnicodeDecodeError, OSError):
            continue

    if not selected_encoding:
        selected_encoding = "latin-1"
        logger.warning(
            "Could not determine encoding for %s. Defaulting to 'latin-1'.",
            file_path.name,
        )

    logger.debug(
        "Reading %s using encoding '%s' (chunk_size=%d)...",
        file_path.name,
        selected_encoding,
        chunk_size,
    )

    reader = pd.read_csv(
        file_path,
        chunksize=chunk_size,
        encoding=selected_encoding,
        low_memory=False,
    )

    for chunk in reader:
        # Attach lineage metadata
        chunk["_source_file_name"] = file_path.name

        if limit is not None:
            remaining = limit - total_yielded
            if remaining <= 0:
                break
            if len(chunk) > remaining:
                chunk = chunk.iloc[:remaining].copy()

        total_yielded += len(chunk)
        yield chunk

        if limit is not None and total_yielded >= limit:
            break
