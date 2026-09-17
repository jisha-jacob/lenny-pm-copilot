import streamlit as st

import retrieval
import answer
import relevance
import sources

st.title("Lenny's PM Copilot")


def answer_question(question: str) -> dict:
    """Run the full pipeline for one question: retrieve grounding chunks,
    generate a cited answer, and render its sources. Returns
    {"answer": str, "sources": list[dict]} (see retrieval.retrieve,
    answer.generate_answer, and sources.render_sources). Raises
    ValueError for an empty/whitespace question without calling either.
    """
    if not question or not question.strip():
        raise ValueError("question must not be empty")

    chunks = retrieval.retrieve(question)
    if not relevance.is_relevant(chunks):
        return {"answer": answer.NOT_ENOUGH_INFO, "sources": []}

    result = answer.generate_answer(question, chunks)
    return {
        "answer": result["answer"],
        "sources": sources.render_sources(result["cited_chunks"]),
    }


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
