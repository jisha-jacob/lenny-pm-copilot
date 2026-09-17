import eval_retrieval


QUESTIONS = [
    {"question": "q1", "expected_video_id": "aaa"},
    {"question": "q2", "expected_video_id": "bbb"},
    {"question": "q3", "expected_video_id": "ccc"},
]


def _chunk(video_id):
    return {"video_id": video_id, "chunk_id": f"{video_id}:ov0.0:0000"}


def test_evaluate_all_hits():
    def retrieve_fn(question, k):
        expected = next(q["expected_video_id"] for q in QUESTIONS if q["question"] == question)
        return [_chunk(expected)]

    result = eval_retrieval.evaluate(QUESTIONS, retrieve_fn)

    assert result["hit_rate"] == 1.0
    assert all(r["hit"] for r in result["results"])


def test_evaluate_all_misses():
    def retrieve_fn(question, k):
        return [_chunk("zzz")]

    result = eval_retrieval.evaluate(QUESTIONS, retrieve_fn)

    assert result["hit_rate"] == 0.0
    assert all(not r["hit"] for r in result["results"])


def test_evaluate_mixed_hits_and_misses():
    def retrieve_fn(question, k):
        if question == "q1":
            return [_chunk("aaa")]
        if question == "q2":
            return [_chunk("zzz")]
        return [_chunk("ccc")]

    result = eval_retrieval.evaluate(QUESTIONS, retrieve_fn)

    assert result["hit_rate"] == 2 / 3
    assert [r["hit"] for r in result["results"]] == [True, False, True]


def test_evaluate_counts_hit_if_expected_id_anywhere_in_top_k():
    def retrieve_fn(question, k):
        return [_chunk("zzz"), _chunk("aaa"), _chunk("yyy")]

    result = eval_retrieval.evaluate([QUESTIONS[0]], retrieve_fn)

    assert result["hit_rate"] == 1.0


def test_evaluate_empty_questions_returns_zero_hit_rate_not_error():
    result = eval_retrieval.evaluate([], lambda q, k: [])

    assert result == {"hit_rate": 0.0, "results": []}


def test_evaluate_passes_k_through_to_retrieve_fn():
    calls = []

    def retrieve_fn(question, k):
        calls.append(k)
        return []

    eval_retrieval.evaluate(QUESTIONS, retrieve_fn, k=3)

    assert calls == [3, 3, 3]
