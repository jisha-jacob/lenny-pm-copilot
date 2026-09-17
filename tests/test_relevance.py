import relevance


def _chunk(distance):
    return {"chunk_id": "x:ov0.0:0000", "video_id": "x", "distance": distance}


def test_is_relevant_false_for_empty_chunks():
    assert relevance.is_relevant([]) is False


def test_is_relevant_true_when_distance_at_or_below_threshold():
    assert relevance.is_relevant([_chunk(relevance.DEFAULT_THRESHOLD)]) is True
    assert relevance.is_relevant([_chunk(relevance.DEFAULT_THRESHOLD - 1)]) is True


def test_is_relevant_false_when_distance_above_threshold():
    assert relevance.is_relevant([_chunk(relevance.DEFAULT_THRESHOLD + 0.01)]) is False


def test_is_relevant_uses_custom_threshold():
    assert relevance.is_relevant([_chunk(5.0)], threshold=4.0) is False
    assert relevance.is_relevant([_chunk(5.0)], threshold=5.0) is True


def test_is_relevant_only_looks_at_nearest_chunk():
    chunks = [_chunk(5.0), _chunk(100.0)]
    assert relevance.is_relevant(chunks, threshold=10.0) is True
