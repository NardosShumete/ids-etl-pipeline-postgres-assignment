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
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

# Processing & Ingestion Constants
DEFAULT_CHUNK_SIZE = 200_000
FALLBACK_ENCODINGS = ["utf-8", "latin-1"]


def get_db_url() -> str:
    """Construct SQLAlchemy database connection URL."""
    return f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def get_db_params() -> dict:
    """Return dictionary of connection parameters for raw psycopg2 connections."""
    return {
        "host": DB_HOST,
        "port": DB_PORT,
        "dbname": DB_NAME,
        "user": DB_USER,
        "password": DB_PASSWORD,
    }
