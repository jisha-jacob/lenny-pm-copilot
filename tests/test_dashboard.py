import dashboard


class FakeCursor:
    def __init__(self, rows=None, one=None):
        self._rows = rows
        self._one = one
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._one


class FakeConn:
    def __init__(self, rows=None, one=None):
        self._cursor = FakeCursor(rows, one)
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


def _patch_db(monkeypatch, rows=None, one=None):
    fake_conn = FakeConn(rows, one)
    monkeypatch.setattr(dashboard.db, "get_connection", lambda: fake_conn)
    return fake_conn


def test_query_volume_by_day_maps_rows(monkeypatch):
    _patch_db(monkeypatch, rows=[("2026-01-01", 3), ("2026-01-02", 5)])

    result = dashboard.query_volume_by_day()

    assert result == [
        {"day": "2026-01-01", "count": 3},
        {"day": "2026-01-02", "count": 5},
    ]


def test_query_volume_by_day_empty_table_returns_empty_list(monkeypatch):
    _patch_db(monkeypatch, rows=[])

    assert dashboard.query_volume_by_day() == []


def test_feedback_ratio_counts_up_and_down(monkeypatch):
    _patch_db(monkeypatch, rows=[("up", 7), ("down", 2)])

    assert dashboard.feedback_ratio() == {"up": 7, "down": 2}


def test_feedback_ratio_defaults_to_zero_when_no_feedback(monkeypatch):
    _patch_db(monkeypatch, rows=[])

    assert dashboard.feedback_ratio() == {"up": 0, "down": 0}


def test_top_cited_episodes_counts_and_sorts(monkeypatch):
    rows = [
        ([{"guest": "A", "title": "T1", "url": "u"}],),
        ([{"guest": "A", "title": "T1", "url": "u"}, {"guest": "B", "title": "T2", "url": "u2"}],),
        ([],),
    ]
    _patch_db(monkeypatch, rows=rows)

    result = dashboard.top_cited_episodes()

    assert result[0] == {"guest": "A", "title": "T1", "count": 2}
    assert result[1] == {"guest": "B", "title": "T2", "count": 1}


def test_top_cited_episodes_respects_limit(monkeypatch):
    rows = [([{"guest": f"G{i}", "title": f"T{i}", "url": "u"}],) for i in range(15)]
    _patch_db(monkeypatch, rows=rows)

    result = dashboard.top_cited_episodes(limit=5)

    assert len(result) == 5


def test_top_cited_episodes_handles_json_string_column(monkeypatch):
    import json

    rows = [(json.dumps([{"guest": "A", "title": "T1", "url": "u"}]),)]
    _patch_db(monkeypatch, rows=rows)

    result = dashboard.top_cited_episodes()

    assert result == [{"guest": "A", "title": "T1", "count": 1}]


def test_top_cited_episodes_empty_table_returns_empty_list(monkeypatch):
    _patch_db(monkeypatch, rows=[])

    assert dashboard.top_cited_episodes() == []


def test_avg_latency_by_day_maps_rows(monkeypatch):
    _patch_db(monkeypatch, rows=[("2026-01-01", 12.5, 456.7)])

    result = dashboard.avg_latency_by_day()

    assert result == [
        {"day": "2026-01-01", "avg_retrieval_ms": 12.5, "avg_generation_ms": 456.7}
    ]


def test_avg_latency_by_day_empty_table_returns_empty_list(monkeypatch):
    _patch_db(monkeypatch, rows=[])

    assert dashboard.avg_latency_by_day() == []


def test_zero_source_question_count_returns_count(monkeypatch):
    _patch_db(monkeypatch, one=(4,))

    assert dashboard.zero_source_question_count() == 4


def test_zero_source_question_count_zero_when_empty_table(monkeypatch):
    _patch_db(monkeypatch, one=(0,))

    assert dashboard.zero_source_question_count() == 0
