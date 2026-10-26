"""Database Initialization and Schema Deployment Module.

This script connects to a PostgreSQL instance, ensures the target database
exists (creating it if necessary), and applies the DDL schema defined in
`sql/01_schema.sql` (creating tables, constraints, and seeding lookup data).

Usage:
    python src/create_database.py
"""

import logging
import os
import sys
from pathlib import Path

# Configure logging with clear, actionable formatting
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("create_database")

# Attempt importing third-party dependencies with helpful troubleshooting advice
try:
    import psycopg2
    from dotenv import load_dotenv
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError as err:
    logger.error(
        "Missing required dependency: %s. "
        "Please install requirements first: pip install -r requirements.txt",
        err,
    )
    sys.exit(1)


def get_project_root() -> Path:
    """Return the absolute path to the project root directory."""
    return Path(__file__).resolve().parent.parent


def load_db_config() -> dict:
    """Load and validate database configuration from .env or environment."""
    root_dir = get_project_root()
    env_path = root_dir / ".env"

    if env_path.is_file():
        load_dotenv(dotenv_path=env_path)
        logger.info("Loaded database configuration from %s", env_path)
    else:
        logger.warning(
            ".env file not found at %s. Falling back to system environment variables.",
            env_path,
        )

    config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "name": os.getenv("DB_NAME", "ids_flows_db"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
    }

    if not config["password"]:
        logger.warning(
            "DB_PASSWORD is empty. Ensure your PostgreSQL configuration permits "
            "passwordless login or update DB_PASSWORD in your .env file."
        )

    return config


def create_database_if_not_exists(config: dict) -> None:
    """Connect to default 'postgres' database and create target database if needed."""
    db_name = config["name"]
    logger.info(
        "Verifying existence of database '%s' on %s:%s...",
        db_name,
        config["host"],
        config["port"],
    )

    try:
        # Connect to maintenance database 'postgres' to check / create DB
        conn = psycopg2.connect(
            host=config["host"],
            port=config["port"],
            dbname="postgres",
            user=config["user"],
            password=config["password"],
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Check if database already exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s;",
            (db_name,),
        )
        exists = cursor.fetchone()

        if not exists:
            logger.info("Database '%s' does not exist. Creating...", db_name)
            # Safe parameterized identifier quoting prevents SQL injection
            create_query = sql.SQL("CREATE DATABASE {} ENCODING 'UTF8';").format(
                sql.Identifier(db_name)
            )
            cursor.execute(create_query)
            logger.info("Database '%s' created successfully.", db_name)
        else:
            logger.info("Database '%s' already exists. Skipping creation.", db_name)

        cursor.close()
        conn.close()

    except psycopg2.OperationalError as err:
        logger.error(
            "Failed to connect to PostgreSQL server at %s:%s. Error: %s\n"
            "Troubleshooting Tips:\n"
            "  1. Is PostgreSQL installed and running?\n"
            "  2. Are the host, port, user, and password in .env correct?\n"
            "  3. Check Windows Services / pg_isready to verify service health.",
            config["host"],
            config["port"],
            err,
        )
        raise


def run_schema_file(config: dict, schema_file: Path) -> None:
    """Execute the DDL schema SQL script against the target database."""
    if not schema_file.is_file():
        raise FileNotFoundError(f"Schema file not found at: {schema_file}")

    logger.info("Reading schema script from: %s", schema_file)
    with open(schema_file, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    logger.info("Connecting to target database '%s' to apply schema...", config["name"])
    conn = psycopg2.connect(
        host=config["host"],
        port=config["port"],
        dbname=config["name"],
        user=config["user"],
        password=config["password"],
    )

    try:
        with conn.cursor() as cursor:
            logger.info("Executing DDL statements from %s...", schema_file.name)
            cursor.execute(schema_sql)
        conn.commit()
        logger.info("Schema applied successfully to database '%s'.", config["name"])
    except Exception as err:
        conn.rollback()
        logger.error("Error executing schema script: %s", err)
        raise
    finally:
        conn.close()


def main() -> None:
    """Main execution flow: load config, ensure database, and execute schema."""
    logger.info("Starting IDS Pipeline Database Setup...")
    try:
        config = load_db_config()
        create_database_if_not_exists(config)

        schema_path = get_project_root() / "sql" / "01_schema.sql"
        run_schema_file(config, schema_path)

        logger.info(
            "Database setup complete! Target '%s' is ready for ETL operations.",
            config["name"],
        )
    except (psycopg2.Error, OSError) as err:
        logger.critical("Database setup aborted due to error: %s", err)
        sys.exit(1)


if __name__ == "__main__":
    main()
