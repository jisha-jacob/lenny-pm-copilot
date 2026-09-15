# Lenny's PM Copilot — Product & Technical Spec (v1)

## 1. Vision

A RAG-based chat app that answers product management questions by retrieving
and synthesizing relevant passages from Lenny's Podcast transcripts
(303 episodes as of grooming issue #3 — corrected from an earlier estimate
of 269; interviews with product/growth leaders). It should feel like asking
a well-read PM friend who's listened to every episode and can point you to
exactly where an idea came from.

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

**Open questions — resolved while grooming issue #3, by inspecting real
transcript files (`ada-chen-rekhi` — a short clip, and `shreyas-doshi` — a
full ~91-minute episode):**

- **Timestamps DO exist per-turn**, contrary to the earlier assumption.
  The body format is: a new speaker turn starts with a line
  `Speaker Name (HH:MM:SS):`, and a same-speaker continuation paragraph
  (the source pre-splits long monologues into multiple paragraph blocks)
  starts with a bare `(HH:MM:SS):` line, no name. This means sources
  (task 6) **can** link to a real timestamp anchor
  (`{youtube_url}&t={seconds}s`) for every chunk, not just the plain
  episode URL — better than the fallback originally planned for.
- **Speaker labels are reliably parseable** via the pattern above — a
  regex like `^(?:(?P<speaker>[^\n(][^\n]*?) )?\((?P<ts>\d{2}:\d{2}:\d{2})\):$`
  on its own line marks the start of each paragraph block, whether a new
  speaker or a continuation.
- **Long speaker turns:** in practice, the source markdown already
  pre-splits long monologues into multiple paragraph blocks (each
  roughly 100–250 words / ~130–350 tokens in the samples checked), so the
  natural unit to chunk on is the **paragraph block**, not the full
  speaker turn. Reaching the 500–800 token target means **grouping
  several consecutive paragraph blocks** (usually spanning more than one
  speaker turn) rather than splitting a single block. Fallback for the
  rare single paragraph block that alone exceeds ~800 tokens: split it at
  sentence boundaries as a secondary pass — not expected to trigger often
  based on the samples checked, but the chunker must not silently fail if
  it does.

## 6. RAG architecture decisions

| Decision | Choice | Rationale |
|---|---|---|
| Chunking | Group consecutive paragraph blocks (see section 5) to ~500-800 tokens per chunk, overlap TBD by eval (see section 8) | Keeps semantic units intact, avoids splitting mid-thought |
| Chunk metadata | guest, episode title, youtube_url, video_id, publish_date, chunk_id, start_timestamp (seconds, from the chunk's first paragraph block) | Needed to build the Sources list, now with a real timestamp anchor (see section 5) |
| Embedding model | `nomic-embed-text` (local, free, 8192-token context) | Chosen over MiniLM: MiniLM's 256-token max would silently truncate our 500–800 token chunks, losing content from most chunks. nomic-embed-text's context comfortably covers a full chunk with no truncation, at similar CPU-only feasibility (~0.3GB vs ~0.1GB) |
| Embedding runtime | [`fastembed`](https://github.com/qdrant/fastembed) (Qdrant's Python library), running `nomic-ai/nomic-embed-text-v1.5` via ONNX Runtime | Decided while grooming issue #3. Ollama would work for local ingestion but can't run as a background service on Streamlit Community Cloud, which retrieval (issue #4) needs at query time — a deployment blocker, not just a preference. Raw `sentence-transformers` + `torch` works everywhere but is a heavy dependency (1-2GB+) for a free-tier deployment target. `fastembed` runs the same model on ONNX Runtime, lightweight enough for Streamlit Community Cloud's resource limits, and is used identically by both ingestion (issue #3) and retrieval (issue #4) so both sides embed with the exact same model/library — no train/serve skew. |
| Vector DB | Postgres 16 + `pgvector` extension, self-managed on GCE `e2-micro` (Always Free) | Consolidates vectors + monitoring into one DB, no separate hosting cost |
| Vector index | None for v1 — exact (brute-force) search | Corpus is small (~5–8K chunks from 303 episodes); exact search answers top-k queries in well under 100ms at this scale and avoids HNSW/IVFFlat build-memory pressure on the 1GB VM. Revisit only if the corpus grows substantially. |
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
  (see section 6 and 11) — a `monitoring` table, not a separate database
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

- **VM:** reuses the existing `pm-playbook-postgres` GCE `e2-micro` instance
  (region `us-central1`, not `us-east1` as originally planned — both are
  Always Free–eligible, so this is a no-cost change), rather than
  provisioning a new VM. This VM already exists and is shared with another
  project (`pm-playbook-db`'s GCP project); this project gets a dedicated
  database and role on it, not a dedicated VM. GCP's Always Free e2-micro
  allowance is one instance per billing account, so provisioning a second
  e2-micro on the same billing account would have incurred real cost —
  reusing the existing instance is what keeps this at $0. Runs Postgres
  only — no app code, no embedding model, to stay well within the VM's 1 GB
  RAM.
- **Database:** a new, dedicated database and low-privilege role on the
  shared VM's Postgres 16 instance (not reusing the other project's
  database or role), with the `pgvector` extension enabled
  (`CREATE EXTENSION vector;`) for that database. Holds both the
  transcript-chunk embeddings table and the `monitoring` table from
  section 9.
- **Memory tuning (1GB VM):** lower `shared_buffers` from Postgres defaults
  to roughly 256MB, and keep `max_connections` low. The Streamlit app
  should use a small connection pool (e.g. 2–5 connections) rather than
  opening a new connection per session — on a shared-core, 1GB instance,
  connection sprawl is a more realistic failure mode than query load.
- **Network security (important on a public VM) — currently NOT achieved,
  see honest caveat below:**
  - A GCE firewall rule (`allow-postgres-lenny-pm-copilot`) was added for
    port 5432, scoped to Streamlit Community Cloud's published outbound IP
    ranges plus the admin's own IP.
  - **This does not actually restrict access.** The VM already has a
    pre-existing rule (`allow-postgres`) allowing `0.0.0.0/0` on port 5432,
    which this project's other database sits behind too. GCP firewall
    allow-rules are additive/permissive — a narrower rule never overrides a
    broader one. As long as `allow-postgres` (`0.0.0.0/0`) exists, **this
    project's Postgres database is reachable from anywhere on the
    internet**, not just from Streamlit/admin, regardless of the new rule.
    Tightening or removing `allow-postgres` is out of scope for issue #2 —
    it risks breaking the other project sharing this VM, and needs its own
    investigation first (see the follow-up issue filed for that). Don't
    read this section as "access is restricted" until that follow-up
    lands.
  - Require SSL for the Postgres connection (`sslmode=require`) and use a
    strong password stored only in Streamlit Cloud's secrets manager
    (`st.secrets`), never committed to the repo.
  - Create a dedicated low-privilege Postgres role for the app (not the
    `postgres` superuser).
  - **Maintenance note:** Streamlit Community Cloud's published outbound
    IPs are not officially guaranteed and may rotate without notice (per
    Streamlit's own docs and community reports — allowlisting is not a
    fully supported Community Cloud feature). If the deployed app suddenly
    loses DB connectivity with no other change, re-fetch the current IP
    list from
    [the Streamlit docs](https://docs.streamlit.io/deploy/streamlit-community-cloud/status)
    and update the GCE firewall rule for port 5432 accordingly.
- **Network tier:** the VM stays on **Premium Tier** (its current setting)
  rather than switching to Standard Tier as originally planned. Switching
  requires removing and re-adding the external access config, which would
  likely change the VM's external IP (`34.135.89.12`, currently ephemeral,
  not a reserved static address) — since the other project sharing this VM
  almost certainly connects using that hardcoded IP, changing it risks
  breaking that project's connectivity. Always Free's network egress
  allowance is only 1GB/month under Premium Tier (vs. 200GiB/month under
  Standard), shared across both projects on this VM — **known risk to
  monitor**, not resolved. If egress usage approaches 1GB/month, revisit
  with a proper reserved static IP (so the tier switch can happen without
  an unplanned IP change) rather than switching tiers under time pressure.
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
  don't mistake it for a production claim. Now sharper since the VM is
  shared with another project: this project's Postgres memory tuning (see
  above) has to coexist with whatever the other project's workload needs,
  not just this project's own light traffic.

## 12. Non-functional notes

- Keep ingestion idempotent (safe to re-run without duplicating chunks),
  mirroring the source repo's own script design.
- The app can also be run fully locally (Postgres via Docker or a local
  install) for development; the Always Free VM is only for the deployed
  portfolio demo.
- No paid infrastructure required except Claude API usage per query.
