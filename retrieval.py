"""Retrieval: turn a user's question into the top-k most relevant
transcript chunks (see issue #4, _docs/plan.md sections 4 and 6).
"""

import db
from embeddings import embed_query

DEFAULT_K = 6

COLUMNS = [
    "chunk_id",
    "guest",
    "title",
    "youtube_url",
    "video_id",
    "publish_date",
    "start_timestamp",
    "chunk_text",
    "distance",
]

SELECT_SQL = """
    SELECT chunk_id, guest, title, youtube_url, video_id, publish_date,
           start_timestamp, chunk_text, embedding <-> %s::vector AS distance
    FROM chunks
    ORDER BY embedding <-> %s::vector
    LIMIT %s;
"""


def retrieve(question: str, k: int = DEFAULT_K) -> list[dict]:
    """Embed `question` and return the top-k most similar chunks, nearest
    first, each with its stored metadata and a distance score (lower is
    more similar -- interpreting that score is issue #9's job, not this
    function's). Raises ValueError for an empty/whitespace question.
    """
    if not question or not question.strip():
        raise ValueError("question must not be empty")

    vector = embed_query(question)

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SELECT_SQL, (vector, vector, k))
            rows = cur.fetchall()
    finally:
        conn.close()

    return [dict(zip(COLUMNS, row)) for row in rows]
