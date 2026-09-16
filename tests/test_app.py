import importlib

import pytest

import app


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

    result = app.answer_question("How does Shreyas think about prioritization?")

    assert result == {
        "answer": "Say no to good ideas.",
        "sources": [{"guest": "Shreyas Doshi", "title": "T", "url": "https://x"}],
    }


def test_answer_question_returns_no_sources_when_nothing_cited(monkeypatch):
    monkeypatch.setattr(app.retrieval, "retrieve", lambda q: [])
    monkeypatch.setattr(
        app.answer,
        "generate_answer",
        lambda q, chunks: {"answer": app.answer.NOT_ENOUGH_INFO, "cited_chunks": []},
    )
    monkeypatch.setattr(app.sources, "render_sources", lambda cited: [])

    result = app.answer_question("something unrelated")

    assert result == {"answer": app.answer.NOT_ENOUGH_INFO, "sources": []}


def test_answer_question_raises_on_empty_question_without_calling_pipeline(monkeypatch):
    calls = []
    monkeypatch.setattr(app.retrieval, "retrieve", lambda q: calls.append(q))
    monkeypatch.setattr(
        app.answer, "generate_answer", lambda q, chunks: calls.append((q, chunks))
    )

    with pytest.raises(ValueError):
        app.answer_question("")
    with pytest.raises(ValueError):
        app.answer_question("   ")

    assert calls == []  # retrieve and generate_answer never called


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

    app.answer_question("a real question")

    assert calls["q"] == "a real question"
    assert calls["chunks"] == [SAMPLE_CHUNK]
