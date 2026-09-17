# Lenny's PM Copilot — MVP Backlog

Derived from `_docs/plan.md` section 10. Each task below is meant to be
handed to someone who has not read the rest of this backlog or the full
spec — background needed to complete the task is included inline.

## 1. Project scaffold
Goal: An empty, runnable Streamlit app with one passing test.
Description: Create a minimal Python project (dependency file, `app.py` entry
point) that runs a blank Streamlit page (`streamlit run app.py`). Add a test
runner (e.g. pytest) with a single trivial passing test to establish the
project's test setup, plus a README stub with local run instructions.

## 2. Provision Postgres + pgvector
Goal: A running, secured Postgres 16 instance with `pgvector` enabled, reachable
from outside the VM.
Description: Provision a GCE `e2-micro` VM (Always Free tier — `us-west1`,
`us-central1`, or `us-east1`), install Postgres 16, and run
`CREATE EXTENSION vector;`. Lock down the firewall for port 5432 to Streamlit
Community Cloud's published outbound IP ranges plus your own admin IP, require
`sslmode=require`, and create a dedicated low-privilege Postgres role for the
app (not the `postgres` superuser). Document the connection details needed
for `st.secrets` later (host, port, db name, role, password).

## 3. Ingestion script
Goal: A script that turns the transcript repo into embedded, stored chunks.
Description: Write a script that reads `episodes/{guest-name}/transcript.md`
files from the `ChatPRD/lennys-podcast-transcripts` GitHub repo (YAML
frontmatter with `guest`, `title`, `youtube_url`, `video_id`, `publish_date`,
plus a full transcript body). Split each transcript into chunks by speaker
turn/paragraph (~500-800 tokens; overlap value TBD — task 8's golden-set
eval should be used to compare 0% vs ~15% overlap and keep whichever
performs better), embed each chunk locally with `nomic-embed-text`, and store
the vector plus metadata (guest, episode title, youtube_url, publish_date,
chunk_id) in the Postgres instance from task 2. Re-running the script must
not create duplicate rows.

## 4. Retrieval function
Goal: A function that turns a question into the top-k most relevant chunks.
Description: Given a user question string, embed it with the same
`nomic-embed-text` model used at ingestion time, then query Postgres via
`pgvector`'s `<->` distance operator for the top-k most similar chunks
(k configurable, default in the 5-8 range). Return each chunk's text plus its
stored metadata (guest, episode title, youtube_url, publish_date). This
function has no UI — it takes a string and returns a list of chunk records.

## 5. Answer generation
Goal: A function that turns retrieved chunks + a question into a grounded answer.
Description: Write a function that takes a user question and a list of
retrieved transcript chunks (from task 4) and calls the OpenAI API
(gpt-4o-mini) to produce an answer. The prompt must instruct the model to
answer only using the provided chunks, not general knowledge. Return the
answer text along with which chunks were actually used/cited, since that
list feeds the sources display in task 6.

## 6. Sources rendering
Goal: A function that renders a clean "Sources" list from cited chunks.
Description: Given the list of chunks an answer actually cited (from task 5),
dedupe them by episode (one entry per episode, even if multiple chunks from
it were used) and produce a display-ready list showing guest name, episode
title, and a link to the episode (`youtube_url`, with a timestamp anchor if
one is available in the chunk metadata, otherwise the plain URL). Only
episodes that contributed a used chunk should appear — no unused/orphan
sources.

## 7. Streamlit chat UI
Goal: A working single-turn chat page wiring retrieval, generation, and sources together.
Description: Build the main Streamlit page: a text input box for the user's
question, a submit action that calls retrieval (task 4) then generation
(task 5), and displays the synthesized answer followed by the sources list
(task 6) below it. Single-turn or simple in-session memory only — no
persistent multi-session history is required.

## 8. Golden-set retrieval eval script
Goal: A script that measures whether retrieval surfaces the right episode.
Description: Create a set of ~15-20 PM questions, each paired with the guest
or episode the answer should draw from (e.g. "How does Shreyas Doshi think
about prioritization?" → the Shreyas Doshi episode). Write a script that runs
each question through the retrieval function (task 4) and reports whether the
expected episode appears in the top-k results, producing an overall hit-rate
number. Also use this script to compare 0% vs ~15% chunk overlap (task 3) and
report which gives the better retrieval hit-rate.

## 9. "No relevant context" fallback
Goal: The app tells the user when it has nothing relevant, instead of guessing.
Description: Add a relevance check on retrieval results (task 4) — e.g. a
similarity-score threshold — and when nothing sufficiently relevant is
retrieved, skip calling the answer-generation step and show the user a
message saying the app doesn't have enough information, rather than letting
the LLM answer from general knowledge.

## 10. LLM prompt-variant eval script
Goal: Pick the better of two answer-generation prompts using the existing golden set.
Description: Reusing the golden-set questions from task 8, write a script
that runs each question through two prompt variants for answer generation
(task 5): a plain "answer from the given context" prompt, and one that also
instructs the model to say "I don't have enough information" when retrieval
confidence is low. Score both variants on answer relevance/groundedness and
record which one should become the default.

## 11. Monitoring table + feedback capture
Goal: Every chat interaction is logged, and users can rate answers.
Description: Add a `monitoring` table to the same Postgres instance used for
vectors (task 2), storing timestamp, question, answer, cited episodes,
retrieval latency, generation latency, and user feedback per interaction.
Add a thumbs up/down widget under each answer in the Streamlit UI (task 7)
that writes the feedback into the corresponding row.

## 12. Monitoring dashboard tab
Goal: A second page in the app showing usage and quality metrics.
Description: Add a second tab/page to the Streamlit app that queries the
`monitoring` table (task 11) directly and renders five charts using
Streamlit's built-in chart elements: query volume over time, thumbs up vs.
down ratio, most-cited episodes/guests (top 10), average retrieval +
generation latency over time, and count of questions that returned zero
retrieved sources.

## 13. Deploy end-to-end
Goal: A publicly reachable, working demo.
Description: Deploy the Streamlit app to Streamlit Community Cloud, pointing
it at the Postgres VM's external IP via `st.secrets` (never committing
credentials to the repo). Verify the firewall/SSL setup from task 2 allows
the connection, then do a full smoke test — ask a question, confirm an
answer with sources appears, and check the monitoring tab — from a fresh
browser session with no prior state.
