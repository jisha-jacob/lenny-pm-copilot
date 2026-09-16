"""Answer generation: turn a question + retrieved chunks (issue #4) into a
grounded answer, citing which chunks were actually used (see issue #5,
_docs/plan.md sections 6 and 7).
"""

import json

import streamlit as st
from openai import OpenAI

MODEL = "gpt-4o-mini"

NOT_ENOUGH_INFO = (
    "I don't have enough information in the podcast transcripts to answer that."
)

SYSTEM_PROMPT = (
    "You are an assistant that answers questions about product management "
    "using ONLY the provided podcast transcript excerpts. Do not use any "
    "outside or general knowledge, even if you know the answer.\n\n"
    "If the excerpts do not contain enough information to answer the "
    "question, say so plainly instead of guessing.\n\n"
    "Respond with a JSON object with exactly two keys:\n"
    '  "answer": your answer text (or a statement that there is not '
    "enough information)\n"
    '  "cited_chunk_ids": a list of the chunk_id values (strings) for the '
    "excerpts you actually drew on to write the answer. Omit any chunk_id "
    "you did not use, and return an empty list if you could not answer "
    "from the excerpts."
)


def _build_user_prompt(question: str, chunks: list[dict]) -> str:
    excerpts = "\n\n".join(
        f"chunk_id: {c['chunk_id']}\n"
        f"guest: {c['guest']}\n"
        f"title: {c['title']}\n"
        f"excerpt: {c['chunk_text']}"
        for c in chunks
    )
    return f"Question: {question}\n\nTranscript excerpts:\n\n{excerpts}"


def _client() -> OpenAI:
    return OpenAI(api_key=st.secrets["openai"]["api_key"])


def generate_answer(question: str, chunks: list[dict]) -> dict:
    """Call the OpenAI API to answer `question` grounded in `chunks` (the
    same record shape retrieval.retrieve returns). Returns a dict with
    `answer` (str) and `cited_chunks` (the subset of `chunks`, in input
    order, that the model says it actually used). Does not call the API
    for an empty chunk list -- there is nothing to ground an answer in.
    """
    if not chunks:
        return {"answer": NOT_ENOUGH_INFO, "cited_chunks": []}

    client = _client()
    response = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(question, chunks)},
        ],
    )
    parsed = json.loads(response.choices[0].message.content)
    cited_ids = set(parsed.get("cited_chunk_ids", []))
    cited_chunks = [c for c in chunks if c["chunk_id"] in cited_ids]

    return {"answer": parsed["answer"], "cited_chunks": cited_chunks}
