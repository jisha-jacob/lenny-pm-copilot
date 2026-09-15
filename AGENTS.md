# AGENTS.md

## Commands

No dependency manifest (`pyproject.toml`, `requirements.txt`, etc.) exists in
this repo yet — the project scaffold is tracked as
[issue #1](https://github.com/jisha-jacob/lenny-pm-copilot/issues/1) and
hasn't landed. Once it does, this section must be updated with the real
commands. Expected shape, per `_docs/plan.md`, once scaffolded:

- Install dependencies: TBD (likely `pip install -r requirements.txt`, to be
  confirmed once issue #1 adds the actual file)
- Run the app locally: TBD (likely `streamlit run app.py`)
- Run the whole test suite: TBD (likely `pytest`)
- Run a single test file: TBD (likely `pytest path/to/test_file.py`)

Do not guess at these commands elsewhere in the codebase or in issue work —
check this file first, and if it's still marked TBD, check the repo directly
for what the scaffold task actually produced.

## Rules

- This project targets **Windows/PowerShell** for local dev. Don't assume a
  Unix shell or Unix-only tooling when writing setup/run instructions.
- Postgres 16 + `pgvector` runs on a GCE VM, not locally, unless a local
  Postgres has been explicitly set up for dev (see `_docs/plan.md` section
  12). Don't assume a local Postgres instance exists.
- Don't add a new dependency without asking first.

## Documents

- [_docs/process.md](_docs/process.md) — how work moves through this
  project (issues, roles, lifecycle)
- [_docs/plan.md](_docs/plan.md) — product & technical spec
- [_docs/team/pm.md](_docs/team/pm.md) — Product Manager role
- [_docs/team/software-engineer.md](_docs/team/software-engineer.md) —
  Software Engineer role
- [_docs/team/qa-engineer.md](_docs/team/qa-engineer.md) — QA Engineer role
