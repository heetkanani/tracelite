# Tracelite AI

Open-source observability for LLM applications. Think Datadog - but built specifically for AI.

tracelite sits between your app and your LLM, capturing every prompt, response, cost, and latency so you can debug, evaluate, and monitor your AI in production.

---

## Features

- **Trace & span ingestion** - capture LLM calls, tool use, and agent steps via a simple SDK
- **Cost tracking** - see per-trace and per-span USD cost at a glance
- **Latency monitoring** - track duration across every span in your pipeline
- **Evaluations** - run automated checks (regex, JSON schema, LLM-as-judge) on every new trace
- **Alerts** - get notified when pass rate drops, cost spikes, or errors exceed a threshold
- **Authentication** - email/password login, session cookies, per-project API keys
- **Self-hosted** - your data stays on your infrastructure

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query |
| Backend | FastAPI, Python 3.11, asyncpg |
| Database | PostgreSQL 15 |
| Infrastructure | Docker Compose |

---

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- [Node.js](https://nodejs.org/) 18+
- [Python](https://www.python.org/) 3.11+

### 1. Clone the repo

```bash
git clone https://github.com/heetkanani/tracelite.git
cd tracelite
```

### 2. Start the database

```bash
docker compose up -d
```

This starts PostgreSQL on port 5432 and runs all migrations automatically.

### 3. Start the backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

The dashboard will be available at `http://localhost:3000`.

### 5. Create your account

Open `http://localhost:3000/signup` and create an account. A default project is created automatically.

### 6. Grab your API key

Go to **Settings** → create an API key. You'll use this to send traces from your app.

---

## Sending Your First Trace

Use the tracelite SDK (or raw HTTP) to send traces from your application.

### Raw HTTP example

```python
import httpx
import uuid

API_KEY = "tl-your-key-here"
BASE_URL = "http://localhost:8000"

trace_id = str(uuid.uuid4())

# Open a trace
httpx.post(f"{BASE_URL}/v1/traces", headers={"X-API-Key": API_KEY}, json={
    "id": trace_id,
    "started_at": "2024-01-01T00:00:00Z",
})

# Add a span
httpx.post(f"{BASE_URL}/v1/spans", headers={"X-API-Key": API_KEY}, json={
    "id": str(uuid.uuid4()),
    "trace_id": trace_id,
    "span_type": "llm",
    "started_at": "2024-01-01T00:00:00Z",
    "ended_at": "2024-01-01T00:00:01Z",
    "input": [{"role": "user", "content": "Hello!"}],
    "output": "Hi there!",
    "model": "gpt-4o",
    "cost_usd": 0.0003,
    "duration_ms": 1000,
    "status": "ok",
})
```

---

## Project Structure

```
tracelite/
├── backend/
│   └── app/
│       ├── main.py          # FastAPI entry point
│       ├── models.py        # Pydantic request/response models
│       ├── queries.py       # All database queries
│       ├── dependencies.py  # Auth dependency injection
│       ├── auth.py          # Password hashing, session tokens
│       ├── db.py            # asyncpg connection pool
│       ├── evaluations.py   # Eval worker (runs checks on new spans)
│       ├── alerts.py        # Alert worker (monitors thresholds)
│       └── routes/
│           ├── traces.py
│           ├── spans.py
│           ├── evals.py
│           ├── alerts.py
│           ├── auth.py
│           └── api_keys.py
├── frontend/
│   └── app/
│       ├── page.tsx         # Traces dashboard
│       ├── evaluations/     # Eval definitions management
│       ├── alerts/          # Alert rules management
│       ├── settings/        # API key management
│       └── traces/[id]/     # Trace detail page
├── migrations/              # SQL migrations (run automatically)
├── docker-compose.yml
└── README.md
```

---

## API Reference

Full interactive API docs are available at `http://localhost:8000/docs` when the backend is running.

### Authentication

All SDK/ingestion endpoints require an `X-API-Key` header:

```
X-API-Key: tl-your-key-here
```

Dashboard endpoints use session cookies set at login.

### Key endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/traces` | Create a trace |
| `POST` | `/v1/spans` | Ingest a span |
| `GET` | `/v1/traces` | List traces (with filters) |
| `GET` | `/v1/traces/{id}` | Get trace detail |
| `GET` | `/v1/evals/definitions` | List eval definitions |
| `POST` | `/v1/evals/definitions` | Create an eval |
| `GET` | `/v1/alerts/rules` | List alert rules |
| `POST` | `/v1/alerts/rules` | Create an alert rule |
| `GET` | `/v1/api-keys` | List API keys |
| `POST` | `/v1/api-keys` | Create an API key |
| `DELETE` | `/v1/api-keys/{id}` | Revoke an API key |
| `POST` | `/v1/auth/signup` | Create account |
| `POST` | `/v1/auth/login` | Log in |
| `POST` | `/v1/auth/logout` | Log out |

---

## Evaluator Types

tracelite supports four built-in evaluator types that run automatically on every new span:

| Type | What it checks | Config example |
|---|---|---|
| `regex_match` | Output matches a regex pattern | `{"pattern": "\\d{3}-\\d{4}"}` |
| `substring_absent` | Output does NOT contain a string | `{"text": "I don't know"}` |
| `json_schema` | Output is valid JSON with required keys | `{"required_keys": ["answer", "source"]}` |
| `llm_judge` | Another LLM grades the output | `{"prompt": "Is this response helpful? Reply YES or NO."}` |

---

## Alert Condition Types

| Type | Triggers when |
|---|---|
| `pass_rate_below` | Eval pass rate drops below a threshold % |
| `cost_per_trace_above` | Average cost per trace exceeds a limit |
| `error_rate_above` | Span error rate exceeds a threshold % |

---

## Development

### Running tests

```bash
cd backend
pytest
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://tracelite:tracelite@localhost:5432/tracelite` | PostgreSQL connection string |
| `SECRET_KEY` | (generated) | Session signing key |

### Resetting the database

```bash
docker compose down -v   # destroys the volume
docker compose up -d     # recreates from scratch
```
---
