"""Configuration management for IDS ETL Pipeline.

Loads environment variables, defines absolute filesystem paths, and sets default
execution parameters (such as chunk sizes and encoding fallbacks).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Base Project Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
DEFAULT_ZIP_PATH = DATA_DIR / "archive.zip"
LOGS_DIR = PROJECT_ROOT / "logs"
SQL_DIR = PROJECT_ROOT / "sql"

# Load environment configuration from .env if present
ENV_FILE = PROJECT_ROOT / ".env"
if ENV_FILE.is_file():
    load_dotenv(dotenv_path=ENV_FILE)

# Database Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "ids_flows_db")


def validate_db_credentials() -> None:
    """Validate required database credentials, raising an error if missing or empty."""
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    if not user:
        raise ValueError(
            "Missing required environment variable: DB_USER is not set or empty. "
            "Please copy .env.example to .env and configure your PostgreSQL credentials."
        )
    if not password:
        raise ValueError(
            "Missing required environment variable: DB_PASSWORD is not set or empty. "
            "Please copy .env.example to .env and configure your PostgreSQL credentials."
        )


# Processing & Ingestion Constants
DEFAULT_CHUNK_SIZE = 200_000
FALLBACK_ENCODINGS = ["utf-8", "latin-1"]


def get_db_url() -> str:
    """Construct SQLAlchemy database connection URL."""
    validate_db_credentials()
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    return f"postgresql+psycopg2://{user}:{password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def get_db_params() -> dict:
    """Return dictionary of connection parameters for raw psycopg2 connections."""
    validate_db_credentials()
    return {
        "host": DB_HOST,
        "port": DB_PORT,
        "dbname": DB_NAME,
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
    }
