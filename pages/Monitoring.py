"""Monitoring dashboard page (issue #12, _docs/plan.md section 9).

Auto-discovered by Streamlit's pages/ convention as a second tab/page
next to app.py.
"""

import pandas as pd
import streamlit as st

import dashboard

st.title("Monitoring")

st.subheader("Query volume over time")
volume = dashboard.query_volume_by_day()
if volume:
    df = pd.DataFrame(volume).set_index("day")
    st.line_chart(df["count"])
else:
    st.write("No interactions logged yet.")

st.subheader("Feedback: thumbs up vs. down")
ratio = dashboard.feedback_ratio()
st.bar_chart(pd.DataFrame([ratio]).T.rename(columns={0: "count"}))

st.subheader("Most-cited episodes (top 10)")
top_episodes = dashboard.top_cited_episodes()
if top_episodes:
    df = pd.DataFrame(top_episodes)
    df["label"] = df["guest"] + " — " + df["title"]
    st.bar_chart(df.set_index("label")["count"])
else:
    st.write("No cited episodes yet.")

st.subheader("Average latency over time")
latency = dashboard.avg_latency_by_day()
if latency:
    df = pd.DataFrame(latency).set_index("day")
    st.line_chart(df[["avg_retrieval_ms", "avg_generation_ms"]])
else:
    st.write("No interactions logged yet.")

st.subheader("Questions with zero retrieved sources")
st.metric("Count", dashboard.zero_source_question_count())
