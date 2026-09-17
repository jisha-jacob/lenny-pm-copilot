"""Monitoring dashboard page (issue #12, _docs/plan.md section 9).

Auto-discovered by Streamlit's pages/ convention as a second tab/page
next to app.py.
"""

import pandas as pd
import streamlit as st

import dashboard
import db

st.title("Monitoring")

data = None
try:
    data = dashboard.fetch_dashboard_data()
except db.DatabaseUnavailableError:
    st.error("Can't reach the database right now — please try again shortly.")

if data is not None:
    st.subheader("Query volume over time")
    volume = data["volume_by_day"]
    if volume:
        df = pd.DataFrame(volume).set_index("day")
        st.line_chart(df["count"])
    else:
        st.write("No interactions logged yet.")

    st.subheader("Feedback: thumbs up vs. down")
    ratio = data["feedback_ratio"]
    st.bar_chart(pd.DataFrame([ratio]).T.rename(columns={0: "count"}))

    st.subheader("Most-cited episodes (top 10)")
    top_episodes = data["top_cited_episodes"]
    if top_episodes:
        df = pd.DataFrame(top_episodes)
        df["label"] = df["guest"] + " — " + df["title"]
        st.bar_chart(df.set_index("label")["count"])
    else:
        st.write("No cited episodes yet.")

    st.subheader("Average latency over time")
    latency = data["avg_latency_by_day"]
    if latency:
        df = pd.DataFrame(latency).set_index("day")
        st.line_chart(df[["avg_retrieval_ms", "avg_generation_ms"]])
    else:
        st.write("No interactions logged yet.")

    st.subheader("Questions with zero retrieved sources")
    st.metric("Count", data["zero_source_question_count"])
