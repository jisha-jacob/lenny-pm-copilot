import logging

import psycopg2
import pytest

import db


def _patch_secrets(monkeypatch):
    monkeypatch.setattr(
        db.st,
        "secrets",
        {
            "postgres": {
                "host": "localhost",
                "port": 5432,
                "dbname": "lenny_pm_copilot",
                "user": "lenny_pm_copilot_app",
                "password": "x",
                "sslmode": "require",
            }
        },
    )


def test_get_connection_raises_database_unavailable_on_operational_error(monkeypatch):
    _patch_secrets(monkeypatch)

    def fake_connect(**kwargs):
        raise psycopg2.OperationalError("could not connect to server")

    monkeypatch.setattr(db.psycopg2, "connect", fake_connect)

    with pytest.raises(db.DatabaseUnavailableError):
        db.get_connection()


def test_get_connection_logs_the_original_error(monkeypatch, caplog):
    _patch_secrets(monkeypatch)

    def fake_connect(**kwargs):
        raise psycopg2.OperationalError("could not connect to server")

    monkeypatch.setattr(db.psycopg2, "connect", fake_connect)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(db.DatabaseUnavailableError):
            db.get_connection()

    assert any("could not connect" in record.message for record in caplog.records)
