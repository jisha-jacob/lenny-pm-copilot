import time

import streamlit as st

import retrieval
import answer
import relevance
import sources
import monitoring

st.title("Lenny's PM Copilot")


def answer_question(question: str) -> dict:
    """Run the full pipeline for one question: retrieve grounding chunks,
    generate a cited answer, render its sources, and log the interaction
    (see retrieval.retrieve, answer.generate_answer, sources.render_sources,
    monitoring.log_interaction). Returns {"answer": str, "sources":
    list[dict], "interaction_id": int}. Raises ValueError for an
    empty/whitespace question without calling any of the above.
    """
    if not question or not question.strip():
        raise ValueError("question must not be empty")

    retrieval_start = time.perf_counter()
    chunks = retrieval.retrieve(question)
    retrieval_latency_ms = (time.perf_counter() - retrieval_start) * 1000

    if not relevance.is_relevant(chunks):
        result = {"answer": answer.NOT_ENOUGH_INFO, "sources": []}
        generation_latency_ms = 0.0
    else:
        generation_start = time.perf_counter()
        generated = answer.generate_answer(question, chunks)
        generation_latency_ms = (time.perf_counter() - generation_start) * 1000
        result = {
            "answer": generated["answer"],
            "sources": sources.render_sources(generated["cited_chunks"]),
        }

    interaction_id = monitoring.log_interaction(
        question=question,
        answer=result["answer"],
        cited_episodes=result["sources"],
        retrieval_latency_ms=retrieval_latency_ms,
        generation_latency_ms=generation_latency_ms,
    )
    result["interaction_id"] = interaction_id
    return result


if "last_result" not in st.session_state:
    st.session_state.last_result = None

with st.form("question_form"):
    question = st.text_input("Ask a product management question")
    submitted = st.form_submit_button("Ask")

if submitted:
    try:
        st.session_state.last_result = answer_question(question)
    except ValueError:
        st.warning("Please enter a question.")

if st.session_state.last_result:
    st.write(st.session_state.last_result["answer"])
    if st.session_state.last_result["sources"]:
        st.subheader("Sources")
        for source in st.session_state.last_result["sources"]:
            st.markdown(f"- [{source['guest']} — {source['title']}]({source['url']})")

    interaction_id = st.session_state.last_result["interaction_id"]
    col1, col2 = st.columns(2)
    if col1.button("👍", key=f"thumbs_up_{interaction_id}"):
        monitoring.record_feedback(interaction_id, "up")
        st.success("Thanks for your feedback!")
    if col2.button("👎", key=f"thumbs_down_{interaction_id}"):
        monitoring.record_feedback(interaction_id, "down")
        st.success("Thanks for your feedback!")
