"""Golden-set retrieval eval (issue #8, _docs/plan.md section 8).

Measures retrieval hit-rate against a golden set of real PM questions, and
compares 0% vs ~15% chunk overlap for those same episodes.

Usage:
    python eval_retrieval.py
"""

import subprocess
import sys

import db
import retrieval
from embeddings import embed_query

COMPARISON_OVERLAP_PCT = 0.15

# Each entry's expected_video_id is a real, currently-ingested episode
# (verified against the chunks table while building this golden set), not
# a fabricated guest/topic. None of these episodes has a known-issue
# overlap override (_docs/known_issues.json) that would already give it a
# non-0% baseline.
GOLDEN_SET = [
    {"question": "How does Shreyas Doshi think about prioritization?", "expected_video_id": "YP_QghPLG-8"},
    {"question": "What growth tactics does Elena Verna say never work?", "expected_video_id": "IHwS2By9UKM"},
    {"question": "What's the ultimate guide to setting OKRs?", "expected_video_id": "kvkL18Ue0dE"},
    {"question": "How do I nail my product positioning?", "expected_video_id": "hdjlCLb9Hl8"},
    {"question": "How do I build better products with continuous product discovery?", "expected_video_id": "9RFaz9ZBXpk"},
    {"question": "What does Marty Cagan mean by product management theater?", "expected_video_id": "9N4ZgNaWvI0"},
    {"question": "What is the ultimate guide to Jobs to Be Done?", "expected_video_id": "xQV7HVyAJjc"},
    {"question": "What's the ultimate guide to A/B testing?", "expected_video_id": "hEzpiDuYFoE"},
    {"question": "What's the art and science of pricing a product?", "expected_video_id": "A6veeCbKIzw"},
    {"question": "Why are most product managers unprepared for the demands of a real startup?", "expected_video_id": "WlRfyEpAKxw"},
    {"question": "How can I become a better decision maker?", "expected_video_id": "svQMODvIGAE"},
    {"question": "What are the 5 essential questions to craft a winning strategy?", "expected_video_id": "y7SN4FK8noY"},
    {"question": "What's the difference between good strategy and bad strategy?", "expected_video_id": "4uWKEG0s9Kc"},
    {"question": "How do I build better product roadmaps?", "expected_video_id": "W3cvqPCGcck"},
    {"question": "How do I build a product strategy stack?", "expected_video_id": "tncs0m5pmQg"},
    {"question": "How should I price my product?", "expected_video_id": "xvQadImf568"},
    {"question": "What are the original growth hacking secrets?", "expected_video_id": "VjJ6xcv7e8s"},
    {"question": "Why will ChatGPT be the next big growth channel?", "expected_video_id": "cX4cL6B-_aU"},
    {"question": "How can I become less distractible and improve my focus?", "expected_video_id": "WSscIIY609c"},
    {"question": "How do I become a category pirate and create a new category?", "expected_video_id": "mS4B541m9xg"},
]


def evaluate(questions: list[dict], retrieve_fn, k: int = retrieval.DEFAULT_K) -> dict:
    """Run each {"question", "expected_video_id"} entry through `retrieve_fn`
    and check whether any returned chunk's video_id matches. Returns
    {"hit_rate": float, "results": [{"question", "expected_video_id",
    "hit": bool}, ...]}.
    """
    results = []
    for item in questions:
        chunks = retrieve_fn(item["question"], k)
        hit = any(c["video_id"] == item["expected_video_id"] for c in chunks)
        results.append(
            {
                "question": item["question"],
                "expected_video_id": item["expected_video_id"],
                "hit": hit,
            }
        )
    hit_count = sum(1 for r in results if r["hit"])
    hit_rate = hit_count / len(results) if results else 0.0
    return {"hit_rate": hit_rate, "results": results}


def _retrieve_scoped_to_overlap(overlap_pct: float):
    """A retrieve_fn(question, k) scoped to only chunks tagged with the
    given overlap_pct, for the overlap comparison below. Kept local to
    this eval script -- retrieval.retrieve's own contract (issue #4) is
    unchanged."""
    tag = f":ov{overlap_pct}:"

    def _retrieve(question: str, k: int) -> list[dict]:
        vector = embed_query(question)
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT chunk_id, guest, title, youtube_url, video_id, publish_date,
                           start_timestamp, chunk_text, embedding <-> %s::vector AS distance
                    FROM chunks
                    WHERE chunk_id LIKE %s
                    ORDER BY embedding <-> %s::vector
                    LIMIT %s;
                    """,
                    (vector, f"%{tag}%", vector, k),
                )
                rows = cur.fetchall()
        finally:
            conn.close()
        return [dict(zip(retrieval.COLUMNS, row)) for row in rows]

    return _retrieve


def ingest_golden_set_overlap_variant(overlap_pct: float = COMPARISON_OVERLAP_PCT) -> None:
    """Ingest an `overlap_pct` variant of just the golden set's own
    episodes, additive via the same {video_id}:ov{overlap_pct}:idx
    chunk_id scheme ingest.py uses -- never touches the existing
    0%-overlap chunks.

    Runs ingest.py itself as one subprocess per episode (not a shared
    embedding loop in this process), matching production ingestion's
    per-episode process isolation -- onnxruntime's CPU provider has a
    documented, unresolved cross-call memory-growth issue that already
    OOM-killed a single process embedding just 12 episodes' chunks (see
    _docs/plan.md section 6); this golden set has 20.
    """
    for item in GOLDEN_SET:
        subprocess.run(
            [
                sys.executable,
                "ingest.py",
                "--overlap-pct",
                str(overlap_pct),
                "--video-id",
                item["expected_video_id"],
            ],
            check=True,
        )


def main() -> None:
    print("=== Golden-set retrieval eval (retrieval.retrieve, live corpus) ===")
    baseline = evaluate(GOLDEN_SET, retrieval.retrieve)
    for r in baseline["results"]:
        status = "HIT " if r["hit"] else "MISS"
        print(f"[{status}] {r['question']} (expected {r['expected_video_id']})")
    hit_count = sum(1 for r in baseline["results"] if r["hit"])
    print(f"Hit rate: {baseline['hit_rate']:.0%} ({hit_count}/{len(baseline['results'])})")

    print(f"\nIngesting {COMPARISON_OVERLAP_PCT:.0%}-overlap variant of golden-set episodes...")
    ingest_golden_set_overlap_variant()

    print("\n=== Overlap comparison (golden-set episodes only) ===")
    ov0 = evaluate(GOLDEN_SET, _retrieve_scoped_to_overlap(0.0))
    ov15 = evaluate(GOLDEN_SET, _retrieve_scoped_to_overlap(COMPARISON_OVERLAP_PCT))
    print(f"0% overlap hit rate:  {ov0['hit_rate']:.0%}")
    print(f"15% overlap hit rate: {ov15['hit_rate']:.0%}")
    if ov15["hit_rate"] > ov0["hit_rate"]:
        print("Better: 15% overlap")
    elif ov0["hit_rate"] > ov15["hit_rate"]:
        print("Better: 0% overlap")
    else:
        print("Better: tie")


if __name__ == "__main__":
    main()
