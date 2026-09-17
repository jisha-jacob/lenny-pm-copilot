"""Interaction logging + feedback capture (issue #11, _docs/plan.md
section 9). Same dedicated Postgres database as the chunks table
(db.get_connection) -- no separate monitoring service.
"""

import json

import db

VALID_FEEDBACK = ("up", "down")


def ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS monitoring (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                cited_episodes JSONB NOT NULL DEFAULT '[]'::jsonb,
                retrieval_latency_ms DOUBLE PRECISION,
                generation_latency_ms DOUBLE PRECISION,
                feedback TEXT
            );
            """
        )
    conn.commit()


def log_interaction(
    question: str,
    answer: str,
    cited_episodes: list[dict],
    retrieval_latency_ms: float,
    generation_latency_ms: float,
) -> int:
    """Insert one interaction row and return its id."""
    conn = db.get_connection()
    try:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO monitoring (
                    question, answer, cited_episodes,
                    retrieval_latency_ms, generation_latency_ms
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    question,
                    answer,
                    json.dumps(cited_episodes),
                    retrieval_latency_ms,
                    generation_latency_ms,
                ),
            )
            interaction_id = cur.fetchone()[0]
        conn.commit()
        return interaction_id
    finally:
        conn.close()


def record_feedback(interaction_id: int, feedback: str) -> None:
    """Update an interaction's feedback column. feedback must be "up" or
    "down"."""
    if feedback not in VALID_FEEDBACK:
        raise ValueError(f"feedback must be one of {VALID_FEEDBACK}, got {feedback!r}")

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE monitoring SET feedback = %s WHERE id = %s;",
                (feedback, interaction_id),
            )
        conn.commit()
    finally:
        conn.close()
