"""Relevance check on retrieval results (issue #9, _docs/plan.md section 7).

DEFAULT_THRESHOLD was chosen empirically while grooming this issue: the
top-1 pgvector `<->` distance for issue #8's 20-question golden set (all
genuinely on-topic PM questions) ranged ~12.1-17.2, while a small sample
of clearly off-topic questions (recipes, car repair, geography, etc.)
ranged ~18.2-20.4. 18.0 sits in that gap.
"""

DEFAULT_THRESHOLD = 18.0


def is_relevant(chunks: list[dict], threshold: float = DEFAULT_THRESHOLD) -> bool:
    """True if the nearest retrieved chunk (chunks[0], since
    retrieval.retrieve orders nearest-first) is close enough to be worth
    answering from. False for an empty chunk list."""
    if not chunks:
        return False
    return chunks[0]["distance"] <= threshold
