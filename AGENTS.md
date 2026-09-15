# AGENTS.md

## Commands

All commands assume PowerShell from the repo root, with a `.venv` virtual
environment (see `README.md` for setup).

- Install dependencies: `pip install -r requirements.txt`
- Run the app locally: `streamlit run app.py`
- Run the whole test suite: `pytest`
- Run a single test file: `pytest tests\test_app.py` (substitute the file)

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
