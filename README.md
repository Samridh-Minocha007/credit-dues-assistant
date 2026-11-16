# credit-dues-assistant

**Concept prototype**: a credit-dues assistant for small neighbourhood shops. Independent concept;
not a Google product. All messages and payments are **simulated**.

See [CLAUDE.md](CLAUDE.md) for the brief and [docs/decisions.md](docs/decisions.md) for design decisions.

## Run locally

Backend (FastAPI + SQLite), from `backend/`:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --reload
```

API docs: http://127.0.0.1:8000/docs. The database file is `backend/dues.db` (git-ignored).
Optional settings go in `backend/.env` (copy `.env.example`).

Frontend (React + Vite), from `frontend/`:

```bash
npm install
npm run dev
```

Open http://localhost:5173.

Tests, from `backend/`:

```bash
.venv/Scripts/python -m pytest
```
