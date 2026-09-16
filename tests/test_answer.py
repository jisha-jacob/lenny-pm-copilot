import json

import answer


SAMPLE_CHUNKS = [
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
    },
    {
        "chunk_id": "def456:ov0.0:0001",
        "guest": "Shreyas Doshi",
        "title": "The art of product management",
        "youtube_url": "https://youtube.com/watch?v=def456",
        "video_id": "def456",
        "publish_date": "2021-01-01",
        "start_timestamp": 90,
        "chunk_text": "Unrelated aside about hiring.",
        "distance": 0.30,
    },
]


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, content):
        self._content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse(self._content)


class FakeChat:
    def __init__(self, content):
        self.completions = FakeCompletions(content)


class FakeClient:
    def __init__(self, content):
        self.chat = FakeChat(content)


def _patch_client(monkeypatch, content):
    fake_client = FakeClient(content)
    monkeypatch.setattr(answer, "_client", lambda: fake_client)
    return fake_client


def test_generate_answer_short_circuits_on_empty_chunks(monkeypatch):
    calls = []
    monkeypatch.setattr(answer, "_client", lambda: calls.append(True))

    result = answer.generate_answer("Any question?", [])

    assert result == {"answer": answer.NOT_ENOUGH_INFO, "cited_chunks": []}
    assert calls == []  # never calls the API


def test_generate_answer_parses_response_and_filters_cited_chunks(monkeypatch):
    content = json.dumps(
        {
            "answer": "Prioritization means saying no to good ideas.",
            "cited_chunk_ids": ["abc123:ov0.0:0000"],
        }
    )
    fake_client = _patch_client(monkeypatch, content)

    result = answer.generate_answer(
        "How does Shreyas think about prioritization?", SAMPLE_CHUNKS
    )

    assert result["answer"] == "Prioritization means saying no to good ideas."
    assert result["cited_chunks"] == [SAMPLE_CHUNKS[0]]
    call = fake_client.chat.completions.calls[0]
    assert call["model"] == answer.MODEL


def test_generate_answer_prompt_includes_question_and_chunk_text(monkeypatch):
    content = json.dumps({"answer": "x", "cited_chunk_ids": []})
    fake_client = _patch_client(monkeypatch, content)

    answer.generate_answer("What about prioritization?", SAMPLE_CHUNKS)

    call = fake_client.chat.completions.calls[0]
    user_message = call["messages"][1]["content"]
    assert "What about prioritization?" in user_message
    assert "Prioritization is about saying no to good ideas." in user_message
    assert SAMPLE_CHUNKS[0]["chunk_id"] in user_message


def test_generate_answer_returns_empty_cited_chunks_when_model_cites_none(monkeypatch):
    content = json.dumps({"answer": answer.NOT_ENOUGH_INFO, "cited_chunk_ids": []})
    _patch_client(monkeypatch, content)

    result = answer.generate_answer("something unrelated", SAMPLE_CHUNKS)

    assert result["cited_chunks"] == []


def test_generate_answer_ignores_unknown_cited_chunk_ids(monkeypatch):
    content = json.dumps(
        {"answer": "x", "cited_chunk_ids": ["not-a-real-id", "abc123:ov0.0:0000"]}
    )
    _patch_client(monkeypatch, content)

    result = answer.generate_answer("q", SAMPLE_CHUNKS)

    assert result["cited_chunks"] == [SAMPLE_CHUNKS[0]]
