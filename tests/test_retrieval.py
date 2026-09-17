import pytest

import db
import retrieval


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params):
        self.executed.append((sql, params))

    def fetchall(self):
        return self._rows


class FakeConn:
    def __init__(self, rows):
        self._cursor = FakeCursor(rows)
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


SAMPLE_ROW = (
    "abc123:ov0.0:0000",
    "Shreyas Doshi",
    "The art of product management",
    "https://youtube.com/watch?v=abc123",
    "abc123",
    "2021-01-01",
    42,
    "Prioritization is about saying no to good ideas.",
    0.12,
)


def _patch_db(monkeypatch, rows):
    fake_conn = FakeConn(rows)
    monkeypatch.setattr(retrieval.db, "get_connection", lambda: fake_conn)
    return fake_conn


def test_retrieve_raises_on_empty_question(monkeypatch):
    calls = []
    monkeypatch.setattr(retrieval, "embed_query", lambda q: calls.append(q))
    with pytest.raises(ValueError):
        retrieval.retrieve("")
    with pytest.raises(ValueError):
        retrieval.retrieve("   ")
    assert calls == []  # never embeds an empty/whitespace question


def test_retrieve_returns_records_with_expected_fields(monkeypatch):
    monkeypatch.setattr(retrieval, "embed_query", lambda q: [0.1, 0.2, 0.3])
    fake_conn = _patch_db(monkeypatch, rows=[SAMPLE_ROW])

    results = retrieval.retrieve("How does Shreyas Doshi think about prioritization?")

    assert results == [
        {
            "chunk_id": "abc123:ov0.0:0000",
            "guest": "Shreyas Doshi",
            "title": "The art of product management",
            "youtube_url": "https://youtube.com/watch?v=abc123",
            "video_id": "abc123",
            "publish_date": "2021-01-01",
            "start_timestamp": 42,
            "chunk_text": "Prioritization is about saying no to good ideas.",
            "distance": 0.12,
        }
    ]
    assert fake_conn.closed


def test_retrieve_orders_by_pgvector_distance_operator(monkeypatch):
    monkeypatch.setattr(retrieval, "embed_query", lambda q: [0.1, 0.2, 0.3])
    fake_conn = _patch_db(monkeypatch, rows=[])

    retrieval.retrieve("some question")

    sql, params = fake_conn._cursor.executed[0]
    assert "<->" in sql
    assert "ORDER BY" in sql


def test_retrieve_passes_k_to_the_query_limit(monkeypatch):
    monkeypatch.setattr(retrieval, "embed_query", lambda q: [0.1, 0.2, 0.3])
    fake_conn = _patch_db(monkeypatch, rows=[])

    retrieval.retrieve("some question", k=3)

    _, params = fake_conn._cursor.executed[0]
    assert params[-1] == 3


def test_retrieve_default_k_is_in_documented_range():
    assert 5 <= retrieval.DEFAULT_K <= 8


def test_retrieve_returns_empty_list_when_no_rows(monkeypatch):
    monkeypatch.setattr(retrieval, "embed_query", lambda q: [0.1, 0.2, 0.3])
    _patch_db(monkeypatch, rows=[])

    assert retrieval.retrieve("anything") == []


def test_retrieve_propagates_database_unavailable_error(monkeypatch):
    monkeypatch.setattr(retrieval, "embed_query", lambda q: [0.1, 0.2, 0.3])

    def fake_get_connection():
        raise db.DatabaseUnavailableError("could not connect to the database")

    monkeypatch.setattr(retrieval.db, "get_connection", fake_get_connection)

    with pytest.raises(db.DatabaseUnavailableError):
        retrieval.retrieve("some question")
