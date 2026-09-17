import importlib

import pytest

import app
import db


def test_app_imports_cleanly():
    importlib.import_module("app")


SAMPLE_CHUNK = {
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


def _stub_log_interaction(monkeypatch, interaction_id=99):
    calls = []
    monkeypatch.setattr(
        app.monitoring,
        "log_interaction",
        lambda **kwargs: calls.append(kwargs) or interaction_id,
    )
    return calls


def test_answer_question_composes_retrieve_generate_and_render(monkeypatch):
    monkeypatch.setattr(app.retrieval, "retrieve", lambda q: [SAMPLE_CHUNK])
    monkeypatch.setattr(
        app.answer,
        "generate_answer",
        lambda q, chunks: {"answer": "Say no to good ideas.", "cited_chunks": chunks},
    )
    monkeypatch.setattr(
        app.sources,
        "render_sources",
        lambda cited: [{"guest": "Shreyas Doshi", "title": "T", "url": "https://x"}],
    )
    _stub_log_interaction(monkeypatch, interaction_id=7)

    result = app.answer_question("How does Shreyas think about prioritization?")

    assert result == {
        "answer": "Say no to good ideas.",
        "sources": [{"guest": "Shreyas Doshi", "title": "T", "url": "https://x"}],
        "interaction_id": 7,
    }


def test_answer_question_returns_no_sources_when_nothing_cited(monkeypatch):
    monkeypatch.setattr(app.retrieval, "retrieve", lambda q: [])
    monkeypatch.setattr(
        app.answer,
        "generate_answer",
        lambda q, chunks: {"answer": app.answer.NOT_ENOUGH_INFO, "cited_chunks": []},
    )
    monkeypatch.setattr(app.sources, "render_sources", lambda cited: [])
    _stub_log_interaction(monkeypatch)

    result = app.answer_question("something unrelated")

    assert result["answer"] == app.answer.NOT_ENOUGH_INFO
    assert result["sources"] == []


def test_answer_question_returns_fallback_without_generating_when_not_relevant(monkeypatch):
    calls = []
    monkeypatch.setattr(app.retrieval, "retrieve", lambda q: [SAMPLE_CHUNK])
    monkeypatch.setattr(app.relevance, "is_relevant", lambda chunks: False)
    monkeypatch.setattr(
        app.answer, "generate_answer", lambda q, chunks: calls.append((q, chunks))
    )
    log_calls = _stub_log_interaction(monkeypatch, interaction_id=5)

    result = app.answer_question("something off-topic")

    assert result["answer"] == app.answer.NOT_ENOUGH_INFO
    assert result["sources"] == []
    assert result["interaction_id"] == 5
    assert calls == []  # generate_answer never called

    assert len(log_calls) == 1
    assert log_calls[0]["question"] == "something off-topic"
    assert log_calls[0]["answer"] == app.answer.NOT_ENOUGH_INFO
    assert log_calls[0]["cited_episodes"] == []
    assert log_calls[0]["generation_latency_ms"] == 0.0


def test_answer_question_still_generates_when_relevant(monkeypatch):
    monkeypatch.setattr(app.retrieval, "retrieve", lambda q: [SAMPLE_CHUNK])
    monkeypatch.setattr(app.relevance, "is_relevant", lambda chunks: True)
    monkeypatch.setattr(
        app.answer,
        "generate_answer",
        lambda q, chunks: {"answer": "Say no to good ideas.", "cited_chunks": chunks},
    )
    monkeypatch.setattr(app.sources, "render_sources", lambda cited: [])
    _stub_log_interaction(monkeypatch)

    result = app.answer_question("How does Shreyas think about prioritization?")

    assert result["answer"] == "Say no to good ideas."


def test_answer_question_logs_interaction_with_latencies_and_sources(monkeypatch):
    monkeypatch.setattr(app.retrieval, "retrieve", lambda q: [SAMPLE_CHUNK])
    monkeypatch.setattr(app.relevance, "is_relevant", lambda chunks: True)
    monkeypatch.setattr(
        app.answer,
        "generate_answer",
        lambda q, chunks: {"answer": "Say no to good ideas.", "cited_chunks": chunks},
    )
    monkeypatch.setattr(
        app.sources,
        "render_sources",
        lambda cited: [{"guest": "Shreyas Doshi", "title": "T", "url": "https://x"}],
    )
    log_calls = _stub_log_interaction(monkeypatch, interaction_id=123)

    result = app.answer_question("How does Shreyas think about prioritization?")

    assert result["interaction_id"] == 123
    assert len(log_calls) == 1
    kwargs = log_calls[0]
    assert kwargs["question"] == "How does Shreyas think about prioritization?"
    assert kwargs["answer"] == "Say no to good ideas."
    assert kwargs["cited_episodes"] == [
        {"guest": "Shreyas Doshi", "title": "T", "url": "https://x"}
    ]
    assert kwargs["retrieval_latency_ms"] >= 0
    assert kwargs["generation_latency_ms"] >= 0


def test_answer_question_raises_on_empty_question_without_calling_pipeline(monkeypatch):
    calls = []
    monkeypatch.setattr(app.retrieval, "retrieve", lambda q: calls.append(q))
    monkeypatch.setattr(
        app.answer, "generate_answer", lambda q, chunks: calls.append((q, chunks))
    )
    monkeypatch.setattr(
        app.monitoring, "log_interaction", lambda **kwargs: calls.append(kwargs)
    )

    with pytest.raises(ValueError):
        app.answer_question("")
    with pytest.raises(ValueError):
        app.answer_question("   ")

    assert calls == []  # retrieve, generate_answer, and log_interaction never called


def test_answer_question_passes_question_and_chunks_through(monkeypatch):
    calls = {}

    def fake_retrieve(q):
        calls["q"] = q
        return [SAMPLE_CHUNK]

    def fake_generate_answer(q, chunks):
        calls["chunks"] = chunks
        return {"answer": "x", "cited_chunks": []}

    monkeypatch.setattr(app.retrieval, "retrieve", fake_retrieve)
    monkeypatch.setattr(app.answer, "generate_answer", fake_generate_answer)
    monkeypatch.setattr(app.sources, "render_sources", lambda cited: [])
    _stub_log_interaction(monkeypatch)

    app.answer_question("a real question")

    assert calls["q"] == "a real question"
    assert calls["chunks"] == [SAMPLE_CHUNK]


def test_answer_question_propagates_database_unavailable_error_from_retrieval(monkeypatch):
    def fake_retrieve(q):
        raise db.DatabaseUnavailableError("could not connect to the database")

    monkeypatch.setattr(app.retrieval, "retrieve", fake_retrieve)

    with pytest.raises(db.DatabaseUnavailableError):
        app.answer_question("How does Shreyas think about prioritization?")


def test_answer_question_still_returns_answer_when_logging_fails(monkeypatch):
    monkeypatch.setattr(app.retrieval, "retrieve", lambda q: [SAMPLE_CHUNK])
    monkeypatch.setattr(
        app.answer,
        "generate_answer",
        lambda q, chunks: {"answer": "Say no to good ideas.", "cited_chunks": chunks},
    )
    monkeypatch.setattr(
        app.sources,
        "render_sources",
        lambda cited: [{"guest": "Shreyas Doshi", "title": "T", "url": "https://x"}],
    )

    def fake_log_interaction(**kwargs):
        raise db.DatabaseUnavailableError("could not connect to the database")

    monkeypatch.setattr(app.monitoring, "log_interaction", fake_log_interaction)

    result = app.answer_question("How does Shreyas think about prioritization?")

    assert result["answer"] == "Say no to good ideas."
    assert result["sources"] == [{"guest": "Shreyas Doshi", "title": "T", "url": "https://x"}]
    assert result["interaction_id"] is None


def test_submit_feedback_returns_true_on_success(monkeypatch):
    calls = []
    monkeypatch.setattr(
        app.monitoring,
        "record_feedback",
        lambda interaction_id, feedback: calls.append((interaction_id, feedback)),
    )

    assert app.submit_feedback(7, "up") is True
    assert calls == [(7, "up")]


def test_submit_feedback_returns_false_when_database_unavailable(monkeypatch):
    def fake_record_feedback(interaction_id, feedback):
        raise db.DatabaseUnavailableError("could not connect to the database")

    monkeypatch.setattr(app.monitoring, "record_feedback", fake_record_feedback)

    assert app.submit_feedback(7, "up") is False
