# credit-dues-assistant

**Concept prototype**: a credit-dues assistant for small neighbourhood shops. Independent concept;
not a Google product. All messages and payments are **simulated**.

See [CLAUDE.md](CLAUDE.md) for the brief, [docs/integration-memo.md](docs/integration-memo.md) for the product
recommendation, and [docs/decisions.md](docs/decisions.md) for design decisions.

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

## Demo shop (generated data)

To explore a realistic shop (60 customers, 120 days of history), generate the demo database and start the
backend in demo mode. Your real data in `backend/dues.db` is never touched.

```bash
cd backend
.venv/Scripts/python -m app.demo_seed
.venv/Scripts/python -m uvicorn app.main:app --env-file demo.env
```

See [docs/demo-script.md](docs/demo-script.md) for a 2-minute walk-through. The data comes from replaying
the app's real rules with simulated customer behaviour, so describe any numbers from it as simulated.

## Pilot with real shops

See [docs/pilot.md](docs/pilot.md): login per shop, hosting on one server with Postgres, offline entry,
data export, and what to measure.

## Use it on your phone (same Wi-Fi)

1. Find your computer's Wi-Fi address: run `ipconfig` and look for "IPv4 Address" (e.g. `192.168.0.27`).
2. In `backend/.env` (git-ignored), set `PUBLIC_BASE_URL=http://<that address>:5173` so payment links open on
   the phone, then restart the backend.
3. Start both servers as usual. On your phone (same Wi-Fi), open `http://<that address>:5173`.

Everything works except the microphone for voice entry and "Add to home screen": browsers only allow those on
HTTPS addresses. A hosted pilot with HTTPS (see docs/pilot.md) has both.
