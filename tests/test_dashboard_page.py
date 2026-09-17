import importlib
import sys

import dashboard
import db


def test_monitoring_page_imports_cleanly(monkeypatch):
    monkeypatch.setattr(dashboard, "query_volume_by_day", lambda: [{"day": "2026-01-01", "count": 3}])
    monkeypatch.setattr(dashboard, "feedback_ratio", lambda: {"up": 2, "down": 1})
    monkeypatch.setattr(
        dashboard,
        "top_cited_episodes",
        lambda limit=10: [{"guest": "A", "title": "T", "count": 2}],
    )
    monkeypatch.setattr(
        dashboard,
        "avg_latency_by_day",
        lambda: [{"day": "2026-01-01", "avg_retrieval_ms": 10.0, "avg_generation_ms": 500.0}],
    )
    monkeypatch.setattr(dashboard, "zero_source_question_count", lambda: 1)

    sys.modules.pop("pages.Monitoring", None)
    sys.modules.pop("pages", None)
    importlib.import_module("pages.Monitoring")


def test_monitoring_page_handles_database_unavailable_without_crashing(monkeypatch):
    def fake_fetch_dashboard_data():
        raise db.DatabaseUnavailableError("could not connect to the database")

    monkeypatch.setattr(dashboard, "fetch_dashboard_data", fake_fetch_dashboard_data)

    sys.modules.pop("pages.Monitoring", None)
    sys.modules.pop("pages", None)
    importlib.import_module("pages.Monitoring")  # must not raise
