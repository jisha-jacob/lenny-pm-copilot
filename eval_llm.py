"""LLM prompt-variant eval (issue #10, _docs/plan.md section 8).

Runs issue #8's golden-set questions through two answer-generation prompt
variants and scores each answer's groundedness/relevance with an LLM
judge, to decide which prompt should be the default (answer.py, issue #5).

Usage:
    python eval_llm.py
"""

import json

import answer
import retrieval
from eval_retrieval import GOLDEN_SET

JUDGE_MODEL = "gpt-4o-mini"

PLAIN_PROMPT = (
    "You are an assistant that answers questions about product management "
    "using the provided podcast transcript excerpts.\n\n"
    "Respond with a JSON object with exactly two keys:\n"
    '  "answer": your answer text\n'
    '  "cited_chunk_ids": a list of the chunk_id values (strings) for the '
    "excerpts you actually drew on to write the answer."
)

# Issue #5's current production prompt, reused directly rather than
# copy-pasted, so this comparison is always against the real default.
FALLBACK_AWARE_PROMPT = answer.SYSTEM_PROMPT

JUDGE_SYSTEM_PROMPT = (
    "You are grading an AI assistant's answer to a product-management "
    "question, given the transcript excerpts it had access to.\n\n"
    "Score the answer from 1 (worst) to 5 (best) on two dimensions:\n"
    '  "groundedness": does the answer only state things supported by the '
    "excerpts, without contradicting or inventing beyond them?\n"
    '  "relevance": does the answer actually address the question asked?\n\n'
    'Respond with JSON: {"groundedness": <1-5 int>, "relevance": <1-5 int>}.'
)


def generate_with_prompt(system_prompt: str, question: str, chunks: list[dict]) -> dict:
    """Same contract as answer.generate_answer, but with a swappable
    system prompt -- for comparing prompt variants, not used in
    production."""
    if not chunks:
        return {"answer": answer.NOT_ENOUGH_INFO, "cited_chunks": []}

    client = answer._client()
    response = client.chat.completions.create(
        model=answer.MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": answer._build_user_prompt(question, chunks)},
        ],
    )
    parsed = json.loads(response.choices[0].message.content)
    cited_ids = set(parsed.get("cited_chunk_ids", []))
    cited_chunks = [c for c in chunks if c["chunk_id"] in cited_ids]
    return {"answer": parsed["answer"], "cited_chunks": cited_chunks}


def score_answer(question: str, chunks: list[dict], generated_answer: str) -> dict:
    """LLM-judge score for one generated answer. Returns
    {"groundedness": int, "relevance": int}, each 1-5."""
    excerpts = "\n\n".join(c["chunk_text"] for c in chunks)
    user_prompt = (
        f"Question: {question}\n\nExcerpts:\n{excerpts}\n\n"
        f"Answer to grade:\n{generated_answer}"
    )
    client = answer._client()
    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return json.loads(response.choices[0].message.content)


def evaluate_prompt_variant(
    system_prompt: str, questions: list[dict] = GOLDEN_SET, k: int = retrieval.DEFAULT_K
) -> dict:
    """Run every question through `system_prompt`, score each answer, and
    return per-question scores plus avg_groundedness/avg_relevance."""
    results = []
    for item in questions:
        chunks = retrieval.retrieve(item["question"], k)
        generated = generate_with_prompt(system_prompt, item["question"], chunks)
        score = score_answer(item["question"], chunks, generated["answer"])
        results.append(
            {
                "question": item["question"],
                "groundedness": score["groundedness"],
                "relevance": score["relevance"],
            }
        )

    if results:
        avg_groundedness = sum(r["groundedness"] for r in results) / len(results)
        avg_relevance = sum(r["relevance"] for r in results) / len(results)
    else:
        avg_groundedness = 0.0
        avg_relevance = 0.0

    return {
        "avg_groundedness": avg_groundedness,
        "avg_relevance": avg_relevance,
        "results": results,
    }


def main() -> None:
    print("=== Variant A: plain ===")
    plain = evaluate_prompt_variant(PLAIN_PROMPT)
    print(
        f"avg groundedness: {plain['avg_groundedness']:.2f}, "
        f"avg relevance: {plain['avg_relevance']:.2f}"
    )

    print("\n=== Variant B: fallback-aware (current production prompt) ===")
    fallback_aware = evaluate_prompt_variant(FALLBACK_AWARE_PROMPT)
    print(
        f"avg groundedness: {fallback_aware['avg_groundedness']:.2f}, "
        f"avg relevance: {fallback_aware['avg_relevance']:.2f}"
    )

    a_total = plain["avg_groundedness"] + plain["avg_relevance"]
    b_total = fallback_aware["avg_groundedness"] + fallback_aware["avg_relevance"]
    print()
    if b_total > a_total:
        print("Winner: fallback-aware prompt (issue #5's current default) -- keep as is.")
    elif a_total > b_total:
        print("Winner: plain prompt -- consider updating answer.py's SYSTEM_PROMPT.")
    else:
        print("Tie.")


if __name__ == "__main__":
    main()
