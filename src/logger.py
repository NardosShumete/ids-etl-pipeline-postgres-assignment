"""Logging setup for IDS ETL Pipeline.

Provides unified logging across console output and persistent file logging
at `logs/etl.log`.
"""

import logging
import sys
from pathlib import Path
from src.config import LOGS_DIR


def setup_logger(
    name: str = "etl_pipeline",
    log_file: Path = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """Configure and return a logger with console and file handlers.

    Args:
        name: Name of the logger instance.
        log_file: Path to destination log file. Defaults to `logs/etl.log`.
        level: Logging severity threshold.

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicate handlers if logger was already initialized
    if logger.handlers:
        return logger

    # Ensure log directory exists
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    if log_file is None:
        log_file = LOGS_DIR / "etl.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    try:
        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as err:
        logger.warning("Could not initialize file logging to %s: %s", log_file, err)

    return logger
