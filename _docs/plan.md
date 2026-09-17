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
- **Non-episode items are intentionally excluded.** Not every folder under
  `episodes/` is a guest interview — e.g. `teaser_2021` is a show trailer
  and lacks `title`/`youtube_url`/`video_id`/`publish_date`. `ingest.py`
  correctly `SKIP`s it via the required-field check; this is expected
  exclusion, not a defect to fix.
- **Corrupted-frontmatter exclusions (guest/title mismatch).** Discovered
  during issue #3 QA reconciliation: some source folders have a `guest`
  field whose name does not appear anywhere in that same file's `title`
  field. In every verified case, the folder's transcript *body* holds
  real, correct content for its stated `guest`, but `title`/`video_id`/
  `youtube_url`/`description` were copy-pasted from an unrelated episode
  (most often a same-`video_id` sibling folder holding the real,
  correctly-labeled episode). Ingesting these rows would attribute a real
  quote to the right guest but link to the wrong YouTube video — the
  citation is not verifiable. Any previously-ingested chunks for these
  folders have been deleted from `chunks`, and they are excluded from
  future ingestion runs (not a `chunking.py`/`ingest.py` bug — the source
  data itself is corrupted). Reason recorded per folder:
  **"guest/title mismatch, corrupted upstream frontmatter, citation not
  verifiable."**
  - `alexander-embiricos`, `interview-q-compilation`, `manik-gupta`,
    `archie-abrams`, `benjamin-mann`, `gibson-biddle`, `brandon-chu`,
    `chip-conley`, `jackie-bavaro`, `david-placek`, `gaurav-misra`,
    `julian-shapiro`, `kim-scott`, `laura-modi`, `ray-cao`,
    `matt-mullenweg`, `nikita-bier`, `ryan-hoover`, `sanchan-saxena`,
    `melissa`
  - Known side effect: because `chunk_id` is keyed by `video_id` + chunk
    index (not guest), several of the *correctly*-labeled sibling
    episodes were partially overwritten by these bad runs before cleanup
    and needed a full re-ingest to restore completeness — done for
    `marty-cagan`, `anneka-gupta`, `matt-lemay`, `benjamin-lauzier`,
    `claire-vo` (all partially overwritten) and `lauryn-isford` (paired
    with `gaurav-misra`, fully overwritten to zero chunks). `melissa`'s
    sibling `melissa-tan` was never actually overwritten in practice (the
    correct content already won every ingestion run), so `melissa` needed
    no chunk deletion — it's excluded purely to prevent a future re-run
    from accidentally clobbering the correct `melissa-tan` content.
    `sanchan-saxena`'s real content had no correctly-named sibling folder
    to fall back on, so that coverage is lost entirely pending upstream
    correction — the only one of these 20 where nothing to date restores
    the real content.
  - `melissa`'s failure mode differs from the other 19: its `guest` field
    (`"Melissa"`) is a bare first name, generic enough to coincidentally
    match the title's `"Melissa Tan"` on a substring check — the original
    guest/title-mismatch screen missed it for that reason. Its actual
    transcript body opens `"Melissa Perri (00:00):"`, a different real
    person entirely. A corpus-wide check for other bare-first-name/
    generic `guest` fields (`boz`, `failure`, `gergely`, `vijay`,
    `hamelshreya`, `yamashata`) found no further cases — all verified
    self-consistent against their transcript body's opening speaker line.
  - **Two pairs are same-guest but genuinely different recordings, not
    duplicates:** `elena-verna-20`/`elena-verna-30` and
    `jake-knapp-john-zeratsky`/`jake-knapp-john-zeratsky-20` share a
    `video_id` with visibly different transcript bodies (confirmed via
    text diff, not just metadata) — two distinct real sessions with the
    same guest(s), not a scrape duplicate. Left as-is, the shared
    `video_id` would let one silently overwrite the other via `chunk_id`
    collision. Fixed by ingesting the previously-losing side
    (`elena-verna-20`, `jake-knapp-john-zeratsky`) at
    `--overlap-pct 0.15` instead of the corpus-standard `0.0`, so its
    `chunk_id`s (which embed the overlap value) no longer collide with
    its sibling's — both sides now coexist in `chunks` under their own
    correct `guest` label. Not a general pattern to repeat casually: this
    works because `0.15` is otherwise unused across the rest of the
    corpus, so it's borrowed here purely as a collision-avoidance value,
    not a real chunking-quality choice for these two episodes.
  - **Checked and left as-is — harmless duplicate-scrape pairs (no action
    needed):** `dr-fei-fei-li`/`fei-fei`, `ethan-evans`/`ethan-evans-20`,
    `hamel-husain-shreya-shankar`/`hamelshreya`,
    `nicole-forsgren`/`nicole-forsgren-20`, `tomer-cohen`/`tomer-cohen-20`,
    `wes-kao`/`wes-kao-20`, `yamashata`/`yuhki-yamashata`. Each pair's
    transcript body was diffed directly (not just metadata) and confirmed
    byte-identical or near-identical — genuinely the same recording
    scraped under two folder names, not a case of distinct content being
    silently collapsed. Only one side survives ingestion (`chunk_id`
    collision), which is fine here since the losing side has nothing
    unique to lose.
  - **Permanent parser gap: `adriel-frederick` has no per-turn
    timestamps.** Discovered via issue #17. Unlike the corrupted-
    frontmatter folders above, this folder's frontmatter is correct — the
    transcript *body* itself never includes a `(TIMESTAMP):` marker on any
    speaker line (just bare `Speaker Name:`), so `chunking.py`'s parser
    (which every other episode in the corpus satisfies, via either
    `HH:MM:SS` or `MM:SS`) correctly extracts zero blocks. Re-checked live
    against all 303 locally cached transcripts while grooming #17:
    `adriel-frederick` is the only episode with this shape (`ryan-hoover`
    also parses to zero blocks but is moot — already excluded above for
    corrupted frontmatter). Excluded in `_docs/known_issues.json` rather
    than special-cased in the parser, since fixing it properly means
    making `chunks.start_timestamp` nullable (a schema change) and
    threading `None` through parsing/chunking for this one episode —
    `sources.py`'s `_anchored_url()` already handles a `None` timestamp by
    falling back to the plain URL, so the display layer is ready for
    this, but the storage layer isn't. Deferred to a follow-up issue
    rather than done as part of #17, since it isn't required for v1 and
    touches the schema; #17 closed with the exclusion only.

## 6. RAG architecture decisions

| Decision | Choice | Rationale |
|---|---|---|
| Chunking | Group consecutive paragraph blocks (see section 5) to ~500-800 tokens per chunk, ~15% overlap | Keeps semantic units intact, avoids splitting mid-thought. Overlap decided by issue #8's golden-set eval: on the 20-question golden set, 15% overlap scored 95% (19/20) retrieval hit-rate vs. 75% (15/20) at 0% overlap -- a clear win, though only measured on the golden set's own 20 episodes, not the full corpus (see issue #19 for the full-corpus version of this comparison). |
| Chunk metadata | guest, episode title, youtube_url, video_id, publish_date, chunk_id, start_timestamp (seconds, from the chunk's first paragraph block) | Needed to build the Sources list, now with a real timestamp anchor (see section 5) |
| Embedding model | `nomic-embed-text` (local, free, 8192-token context) | Chosen over MiniLM: MiniLM's 256-token max would silently truncate our 500–800 token chunks, losing content from most chunks. nomic-embed-text's context comfortably covers a full chunk with no truncation, at similar CPU-only feasibility (~0.3GB vs ~0.1GB) |
| Embedding runtime | [`fastembed`](https://github.com/qdrant/fastembed) (Qdrant's Python library), running `nomic-ai/nomic-embed-text-v1.5` via ONNX Runtime | Decided while grooming issue #3. Ollama would work for local ingestion but can't run as a background service on Streamlit Community Cloud, which retrieval (issue #4) needs at query time — a deployment blocker, not just a preference. Raw `sentence-transformers` + `torch` works everywhere but is a heavy dependency (1-2GB+) for a free-tier deployment target. `fastembed` runs the same model on ONNX Runtime, lightweight enough for Streamlit Community Cloud's resource limits, and is used identically by both ingestion (issue #3) and retrieval (issue #4) so both sides embed with the exact same model/library — no train/serve skew. |
| Embedding session settings | `fastembed`'s `TextEmbedding(..., threads=1, enable_cpu_mem_arena=False)`, plus a small `.embed(..., batch_size=8)` | Found while implementing issue #3: onnxruntime's CPU provider defaults (multi-threaded, growable memory arena, batch_size=256) caused an OOM kill embedding even a single episode's chunks on a memory-constrained machine. These settings fixed that spike. Both `embeddings.py` functions (`embed_documents` and `embed_query`) use them, so retrieval (issue #4) gets the same protection at query time on Streamlit Community Cloud, not just ingestion. |
| Embedding process lifetime (ingestion only) | One `ingest.py` subprocess per episode, not one process for the whole run | Separate from the settings above: onnxruntime's CPU provider has a known, unresolved memory-growth issue across repeated inference calls in one long-lived process (see e.g. [onnxruntime#9313](https://github.com/microsoft/onnxruntime/issues/9313), [#22271](https://github.com/microsoft/onnxruntime/issues/22271), [#26831](https://github.com/microsoft/onnxruntime/issues/26831) — no real fix exists, "restart the process" is the community's own workaround). Confirmed directly: a single process embedding 12 episodes' worth of chunks grew to 1.5GB RSS and was OOM-killed on this machine, despite the settings fix above. Running one fresh subprocess per episode lets the OS fully reclaim memory between episodes. **Residual risk for retrieval (issue #4):** a long-lived Streamlit process serving many queries over time could accumulate the same way, just far more slowly (one query's embed call vs. looping over hundreds of chunks) — worth watching via the monitoring dashboard (section 9) rather than assumed to be a non-issue. |
| Vector DB | Postgres 16 + `pgvector` extension, self-managed on GCE `e2-micro` (Always Free) | Consolidates vectors + monitoring into one DB, no separate hosting cost |
| Vector index | None for v1 — exact (brute-force) search | Corpus is small (~5–8K chunks from 303 episodes); exact search answers top-k queries in well under 100ms at this scale and avoids HNSW/IVFFlat build-memory pressure on the 1GB VM. Revisit only if the corpus grows substantially. |
| Retrieval | Top-k plain vector similarity (k=5–8, tune during QA) via `pgvector` `<->` distance | Simplest working v1; leaves room for hybrid later |
| Answer LLM | OpenAI (`gpt-4o-mini`) | Account already available |
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
5. Answer generation — chunks + question → OpenAI API (gpt-4o-mini) → answer
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
  free for public apps. Only ongoing cost is OpenAI API (gpt-4o-mini) usage per query.
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
- No paid infrastructure required except OpenAI API (gpt-4o-mini) usage per query.
