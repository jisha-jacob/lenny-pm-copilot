import eval_llm


QUESTIONS = [
    {"question": "q1", "expected_video_id": "aaa"},
    {"question": "q2", "expected_video_id": "bbb"},
]


def test_evaluate_prompt_variant_averages_scores(monkeypatch):
    monkeypatch.setattr(eval_llm.retrieval, "retrieve", lambda q, k: [{"chunk_id": "x"}])
    monkeypatch.setattr(
        eval_llm, "generate_with_prompt", lambda prompt, q, chunks: {"answer": "a", "cited_chunks": []}
    )

    scores = {"q1": {"groundedness": 4, "relevance": 2}, "q2": {"groundedness": 2, "relevance": 4}}
    monkeypatch.setattr(
        eval_llm, "score_answer", lambda q, chunks, generated_answer: scores[q]
    )

    result = eval_llm.evaluate_prompt_variant("some prompt", questions=QUESTIONS)

    assert result["avg_groundedness"] == 3.0
    assert result["avg_relevance"] == 3.0
    assert len(result["results"]) == 2


def test_evaluate_prompt_variant_empty_questions_returns_zero_averages(monkeypatch):
    monkeypatch.setattr(eval_llm.retrieval, "retrieve", lambda q, k: [])
    monkeypatch.setattr(eval_llm, "generate_with_prompt", lambda prompt, q, chunks: {})
    monkeypatch.setattr(eval_llm, "score_answer", lambda q, chunks, a: {})

    result = eval_llm.evaluate_prompt_variant("some prompt", questions=[])

    assert result == {"avg_groundedness": 0.0, "avg_relevance": 0.0, "results": []}


def test_evaluate_prompt_variant_passes_question_and_chunks_through(monkeypatch):
    calls = {}

    def fake_retrieve(q, k):
        calls["retrieve_q"] = q
        return [{"chunk_id": "x"}]

    def fake_generate(prompt, q, chunks):
        calls["generate_args"] = (prompt, q, chunks)
        return {"answer": "the answer", "cited_chunks": []}

    def fake_score(q, chunks, generated_answer):
        calls["score_args"] = (q, chunks, generated_answer)
        return {"groundedness": 5, "relevance": 5}

    monkeypatch.setattr(eval_llm.retrieval, "retrieve", fake_retrieve)
    monkeypatch.setattr(eval_llm, "generate_with_prompt", fake_generate)
    monkeypatch.setattr(eval_llm, "score_answer", fake_score)

    eval_llm.evaluate_prompt_variant("my prompt", questions=[QUESTIONS[0]])

    assert calls["retrieve_q"] == "q1"
    assert calls["generate_args"] == ("my prompt", "q1", [{"chunk_id": "x"}])
    assert calls["score_args"] == ("q1", [{"chunk_id": "x"}], "the answer")


def test_generate_with_prompt_short_circuits_on_empty_chunks(monkeypatch):
    calls = []
    monkeypatch.setattr(eval_llm.answer, "_client", lambda: calls.append(True))

    result = eval_llm.generate_with_prompt("some prompt", "a question", [])

    assert result == {"answer": eval_llm.answer.NOT_ENOUGH_INFO, "cited_chunks": []}
    assert calls == []
