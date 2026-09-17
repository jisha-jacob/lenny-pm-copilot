import pytest

import db
import monitoring


class FakeCursor:
    def __init__(self, fetch_result=None):
        self._fetch_result = fetch_result
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self._fetch_result


class FakeConn:
    def __init__(self, fetch_result=None):
        self._cursor = FakeCursor(fetch_result)
        self.closed = False
        self.committed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def _patch_db(monkeypatch, fetch_result=None):
    fake_conn = FakeConn(fetch_result)
    monkeypatch.setattr(monitoring.db, "get_connection", lambda: fake_conn)
    return fake_conn


def test_ensure_schema_creates_table_and_commits():
    conn = FakeConn()

    monitoring.ensure_schema(conn)

    sql, _ = conn._cursor.executed[0]
    assert "CREATE TABLE IF NOT EXISTS monitoring" in sql
    assert conn.committed


def test_log_interaction_inserts_row_and_returns_id(monkeypatch):
    fake_conn = _patch_db(monkeypatch, fetch_result=(42,))

    interaction_id = monitoring.log_interaction(
        question="How does Shreyas think about prioritization?",
        answer="Say no to good ideas.",
        cited_episodes=[{"guest": "Shreyas Doshi", "title": "T", "url": "https://x"}],
        retrieval_latency_ms=12.3,
        generation_latency_ms=456.7,
    )

    assert interaction_id == 42
    assert fake_conn.committed
    assert fake_conn.closed
    insert_sql, params = fake_conn._cursor.executed[-1]
    assert "INSERT INTO monitoring" in insert_sql
    assert params[0] == "How does Shreyas think about prioritization?"
    assert params[1] == "Say no to good ideas."
    assert params[3] == 12.3
    assert params[4] == 456.7


def test_log_interaction_ensures_schema_before_inserting(monkeypatch):
    fake_conn = _patch_db(monkeypatch, fetch_result=(1,))

    monitoring.log_interaction("q", "a", [], 1.0, 2.0)

    sqls = [sql for sql, _ in fake_conn._cursor.executed]
    assert any("CREATE TABLE IF NOT EXISTS monitoring" in sql for sql in sqls)
    assert any("INSERT INTO monitoring" in sql for sql in sqls)


def test_record_feedback_updates_row(monkeypatch):
    fake_conn = _patch_db(monkeypatch)

    monitoring.record_feedback(42, "up")

    sql, params = fake_conn._cursor.executed[-1]
    assert "UPDATE monitoring" in sql
    assert params == ("up", 42)
    assert fake_conn.committed
    assert fake_conn.closed


def test_record_feedback_rejects_invalid_value(monkeypatch):
    _patch_db(monkeypatch)

    with pytest.raises(ValueError):
        monitoring.record_feedback(42, "sideways")


def test_log_interaction_propagates_database_unavailable_error(monkeypatch):
    def fake_get_connection():
        raise db.DatabaseUnavailableError("could not connect to the database")

    monkeypatch.setattr(monitoring.db, "get_connection", fake_get_connection)

    with pytest.raises(db.DatabaseUnavailableError):
        monitoring.log_interaction("q", "a", [], 1.0, 2.0)


def test_record_feedback_propagates_database_unavailable_error(monkeypatch):
    def fake_get_connection():
        raise db.DatabaseUnavailableError("could not connect to the database")

    monkeypatch.setattr(monitoring.db, "get_connection", fake_get_connection)

    with pytest.raises(db.DatabaseUnavailableError):
        monitoring.record_feedback(42, "up")
