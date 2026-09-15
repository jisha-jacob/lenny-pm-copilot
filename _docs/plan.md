# Lenny's PM Copilot — Product & Technical Spec (v1)

## 1. Vision

A RAG-based chat app that answers product management questions by retrieving
and synthesizing relevant passages from Lenny's Podcast transcripts
(269 episodes, interviews with product/growth leaders). It should feel like
asking a well-read PM friend who's listened to every episode and can point
you to exactly where an idea came from.

## 2. Users

- Individual contributor and early-career PMs looking for tactical advice
  ("how do I run a good PRFAQ", "how do I prioritize a roadmap")
- No auth/multi-user requirements for v1 — single-user local/personal tool

## 3. Core user story (v1)

> As a PM, I type a question into a Streamlit chat box. The app retrieves the
> most relevant transcript chunks, sends them + my question to an LLM, and
> shows me a synthesized answer. Below the answer, I see a "Sources" section
> listing the guest name, episode title, and a link back to the YouTube
> episode (with timestamp if available) for every chunk that was actually
> used.

## 4. Out of scope for v1

- User accounts / auth / multi-user history
- Conversation memory across sessions (single-turn or simple in-session
  memory only)
- Inline citations mid-answer (sources list at the end instead — decided)
- Hybrid keyword+vector search (plain vector search for v1; architecture
  should not block adding this later)
- Fine-tuning any model
- Ingesting new episodes automatically (manual/scripted re-run of ingestion
  is fine)
- Hybrid search, document re-ranking, query rewriting, containerization —
  these are "bonus" items in the LLM Zoomcamp evaluation rubric
  (https://github.com/DataTalksClub/llm-zoomcamp/blob/main/project.md) but
  add complexity without changing whether the app answers questions well.
  Deferred to a possible v2. (Cloud deployment, also a bonus item, **is**
  in scope — see section 11.)

## 5. Data source

Repo: `ChatPRD/lennys-podcast-transcripts` (GitHub)

```
episodes/{guest-name}/transcript.md   # YAML frontmatter + full transcript
index/                                 # topic index, not required for v1
```

Frontmatter fields available per episode: `guest`, `title`, `youtube_url`,
`video_id`, `publish_date`, `description`, `duration_seconds`, `duration`,
`view_count`, `channel`.

**Open question to resolve during ingestion task grooming:** transcripts do
not appear to carry per-line timestamps in the raw markdown — confirm this
when the ingestion task is implemented. If no timestamps exist, sources will
link to the episode's `youtube_url` without a timestamp anchor (acceptable
fallback for v1).

## 6. RAG architecture decisions

| Decision | Choice | Rationale |
|---|---|---|
| Chunking | By speaker turn / paragraph, ~500-800 tokens per chunk with ~15% overlap | Keeps semantic units intact, avoids splitting mid-thought |
| Chunk metadata | guest, episode title, youtube_url, publish_date, chunk_id | Needed to build the Sources list |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` (local, free) | Zero ingestion cost for ~269 transcripts |
| Vector DB | Postgres 16 + `pgvector` extension, self-managed on GCE `e2-micro` (Always Free) | Consolidates vectors + monitoring into one DB, no separate hosting cost |
| Retrieval | Top-k plain vector similarity (k=5–8, tune during QA) via `pgvector` `<->` distance | Simplest working v1; leaves room for hybrid later |
| Answer LLM | Claude (Anthropic API) | Matches Claude Code tooling already in use |
| Citation format | Sources list at end of answer: guest, episode title, link | Decided — not inline |
| Frontend | Streamlit | Decided |
| App hosting | Streamlit Community Cloud (free), connecting to Postgres on the VM over the network | Keeps the 1GB-RAM VM dedicated to Postgres only; avoids RAM contention with the embedding model and Streamlit process |
| Data hosting | Self-managed Postgres 16 on GCE `e2-micro` (Always Free tier) | Free, and doubles as vector store + monitoring store — see section 9 and 11 |

## 7. Answer quality / grounding rules

- The LLM must only answer from retrieved chunks — if retrieval returns
  nothing relevant, the app should say so rather than let the LLM answer
  from general knowledge.
- Every episode that contributed a chunk actually used in the answer must
  appear in the Sources list (no orphan/unused sources listed).

## 8. Success criteria / eval approach

- Build a small golden set (~15–20 PM questions) with the expected
  guest/episode each answer should draw from (e.g. "How does Shreyas Doshi
  think about prioritization?" → should surface the Shreyas Doshi episode).
- QA agent checks: did retrieval surface the expected episode in top-k, and
  does the final answer's Sources list include it.
- This becomes the basis of the QA engineer role's acceptance-criteria
  checks for retrieval-related tasks.
- **LLM output evaluation (reuses the same golden set, no extra cost):** run
  the golden-set questions through 2 prompt variants (e.g. a plain
  "answer from context" prompt vs. one that also instructs the model to
  say "I don't have enough information" when retrieval confidence is low),
  score both on answer relevance/groundedness, and keep the better one as
  default. This can be a single eval script (`eval/llm_eval.py`) — no new
  tool or service required.

## 9. Monitoring & feedback (consolidated into Postgres)

Added per the LLM Zoomcamp evaluation rubric's "Monitoring" criterion
(https://github.com/DataTalksClub/llm-zoomcamp/blob/main/project.md).

- **Storage:** same self-managed Postgres 16 instance used for `pgvector`
  (see section 6 and 12) — a `monitoring` table, not a separate database
  service. One DB to run and back up.
- **What gets logged per interaction:** timestamp, question, answer,
  episodes cited, retrieval latency, generation latency, and user
  feedback (👍/👎 buttons under each answer).
- **Feedback capture:** thumbs up/down widget under every answer, written
  to the same `monitoring` row as the interaction.
- **Dashboard:** a second tab/page in the *same* Streamlit app (no separate
  Grafana/Kibana instance) using Streamlit's built-in `st.bar_chart` /
  `st.line_chart` / `st.metric`, querying the `monitoring` table directly.
  Five charts is enough to meet the rubric's top tier:
  1. Query volume over time (line chart, count per day)
  2. Thumbs up vs. thumbs down ratio (bar chart)
  3. Most-cited episodes/guests (bar chart, top 10)
  4. Average retrieval + generation latency over time (line chart)
  5. Questions with zero retrieved sources — i.e. potential gaps in the
     knowledge base (table or bar chart by count)
- **Cost:** $0 — reuses the same Always Free Postgres VM; no new service.

## 10. MVP backlog seed (to be refined into GitHub issues)

1. Project scaffold — empty Streamlit app + passing test
2. Provision GCE `e2-micro` VM, install Postgres 16 + `pgvector`, lock down
   access (see section 12)
3. Ingestion script — parse `episodes/*/transcript.md`, chunk, embed, store
   in Postgres via `pgvector`
4. Retrieval function — query → top-k chunks via `pgvector` distance search
5. Answer generation — chunks + question → Claude API → answer
6. Sources rendering — dedupe chunks by episode, render guest/title/link
7. Streamlit chat UI — input box, answer display, sources section
8. Golden-set eval script — run golden questions, report retrieval hit-rate
9. "No relevant context" fallback handling
10. LLM prompt-variant eval script — run golden set through 2 prompts, pick default
11. Postgres `monitoring` table + thumbs up/down feedback capture
12. Monitoring tab in Streamlit — 5 charts read from the `monitoring` table
13. Deploy: connect Streamlit Community Cloud to the Postgres VM, set
    connection secrets, verify end-to-end from a fresh browser session

## 11. Deployment (GCE Always Free VM + Streamlit Community Cloud)

**Goal:** get a working, publicly reachable demo for the portfolio at zero
hosting cost.

- **VM:** GCE `e2-micro` in an Always Free–eligible region (`us-west1`,
  `us-central1`, or `us-east1`). Runs Postgres 16 only — no app code, no
  embedding model, to stay well within the VM's 1 GB RAM.
- **Database:** Postgres 16 with the `pgvector` extension enabled
  (`CREATE EXTENSION vector;`), holding both the transcript-chunk
  embeddings table and the `monitoring` table from section 9.
- **Network security (important on a public VM):**
  - Do **not** leave Postgres open to `0.0.0.0/0`. Restrict the GCE
    firewall rule for port 5432 to Streamlit Community Cloud's published
    outbound IP ranges (check current ranges at deploy time) plus your own
    IP for admin access.
  - Require SSL for the Postgres connection (`sslmode=require`) and use a
    strong password stored only in Streamlit Cloud's secrets manager
    (`st.secrets`), never committed to the repo.
  - Create a dedicated low-privilege Postgres role for the app (not the
    `postgres` superuser).
- **App:** deploy the Streamlit app to Streamlit Community Cloud, pointed
  at the VM's external IP via `st.secrets`. Community Cloud gives more RAM
  headroom than the `e2-micro`, which matters since the embedding model
  runs in the app process at query time.
- **Cost:** $0 — GCE `e2-micro` and Postgres are inside the Always Free
  tier limits (1 non-preemptible `e2-micro` per month in eligible US
  regions, 30 GB standard persistent disk); Streamlit Community Cloud is
  free for public apps. Only ongoing cost is Claude API usage per query.
- **Known trade-off:** `e2-micro` is a shared-core, 1 GB RAM instance —
  fine for a portfolio-scale demo with light traffic, but not sized for
  production load. Worth stating explicitly in the README so reviewers
  don't mistake it for a production claim.

## 12. Non-functional notes

- Keep ingestion idempotent (safe to re-run without duplicating chunks),
  mirroring the source repo's own script design.
- The app can also be run fully locally (Postgres via Docker or a local
  install) for development; the Always Free VM is only for the deployed
  portfolio demo.
- No paid infrastructure required except Claude API usage per query.
