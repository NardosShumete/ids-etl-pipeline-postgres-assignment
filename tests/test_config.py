"""Unit tests verifying configuration validation and security checks."""

import pytest

from src.config import get_db_params, get_db_url, validate_db_credentials


def test_config_missing_password_raises_error(monkeypatch):
    """Verify that a missing or empty DB_PASSWORD raises ValueError with helpful message."""
    monkeypatch.setenv("DB_USER", "postgres")
    monkeypatch.delenv("DB_PASSWORD", raising=False)

    with pytest.raises(ValueError, match="DB_PASSWORD is not set or empty"):
        validate_db_credentials()

    with pytest.raises(ValueError, match="DB_PASSWORD is not set or empty"):
        get_db_params()

    with pytest.raises(ValueError, match="DB_PASSWORD is not set or empty"):
        get_db_url()


def test_config_empty_password_raises_error(monkeypatch):
    """Verify that an explicitly empty DB_PASSWORD ('') raises ValueError."""
    monkeypatch.setenv("DB_USER", "postgres")
    monkeypatch.setenv("DB_PASSWORD", "")

    with pytest.raises(ValueError, match="DB_PASSWORD is not set or empty"):
        validate_db_credentials()


def test_config_missing_user_raises_error(monkeypatch):
    """Verify that a missing or empty DB_USER raises ValueError."""
    monkeypatch.delenv("DB_USER", raising=False)
    monkeypatch.setenv("DB_PASSWORD", "secret")

    with pytest.raises(ValueError, match="DB_USER is not set or empty"):
        validate_db_credentials()
