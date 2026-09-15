# Lenny's PM Copilot

A RAG-based chat app that answers product management questions by
retrieving and synthesizing relevant passages from Lenny's Podcast
transcripts. See [`_docs/plan.md`](_docs/plan.md) for the full spec.

## Local setup (Windows/PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the app

```powershell
streamlit run app.py
```

## Run tests

```powershell
pytest
```

Run a single test file with:

```powershell
pytest tests\test_app.py
```
