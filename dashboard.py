"""Monitoring dashboard queries (issue #12, _docs/plan.md section 9).

Pure data-fetching functions against the monitoring table (issue #11) --
no Streamlit calls here, so they're testable against a mocked DB
connection like the rest of this codebase. pages/Monitoring.py renders
their results.
"""

import json
from collections import Counter

import db


def query_volume_by_day() -> list[dict]:
    """{"day", "count"}, one row per day with >=1 interaction, ordered by
    day."""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT created_at::date AS day, count(*) AS count
                FROM monitoring
                GROUP BY day
                ORDER BY day;
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [{"day": day, "count": count} for day, count in rows]


def feedback_ratio() -> dict:
    """{"up": int, "down": int} counts across interactions with non-null
    feedback."""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT feedback, count(*)
                FROM monitoring
                WHERE feedback IS NOT NULL
                GROUP BY feedback;
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    counts = {"up": 0, "down": 0}
    for feedback, count in rows:
        counts[feedback] = count
    return counts


def top_cited_episodes(limit: int = 10) -> list[dict]:
    """{"guest", "title", "count"}, counting how many interactions cited
    each distinct (guest, title) episode across all rows' cited_episodes,
    most-cited first, capped at `limit`."""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT cited_episodes FROM monitoring;")
            rows = cur.fetchall()
    finally:
        conn.close()

    tally: Counter = Counter()
    for (cited_episodes,) in rows:
        episodes = (
            json.loads(cited_episodes)
            if isinstance(cited_episodes, str)
            else cited_episodes
        )
        for episode in episodes:
            tally[(episode["guest"], episode["title"])] += 1

    return [
        {"guest": guest, "title": title, "count": count}
        for (guest, title), count in tally.most_common(limit)
    ]


def avg_latency_by_day() -> list[dict]:
    """{"day", "avg_retrieval_ms", "avg_generation_ms"}, one row per day,
    ordered by day."""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT created_at::date AS day,
                       avg(retrieval_latency_ms) AS avg_retrieval_ms,
                       avg(generation_latency_ms) AS avg_generation_ms
                FROM monitoring
                GROUP BY day
                ORDER BY day;
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {"day": day, "avg_retrieval_ms": avg_retrieval, "avg_generation_ms": avg_generation}
        for day, avg_retrieval, avg_generation in rows
    ]


def zero_source_question_count() -> int:
    """Count of interactions whose cited_episodes is an empty list --
    potential gaps in the knowledge base."""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM monitoring WHERE cited_episodes = '[]'::jsonb;"
            )
            (count,) = cur.fetchone()
    finally:
        conn.close()
    return count
