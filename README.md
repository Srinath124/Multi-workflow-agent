# AI Incident Response Engineer

> Production-ready AI agent with persistent memory, intelligent runtime routing, and full DevOps pipeline.

![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![Tests](https://img.shields.io/badge/Tests-14%20Passing-brightgreen)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![Next.js](https://img.shields.io/badge/Next.js-15-black)

---

## What This Is

Not another chatbot. An **AI employee** that:

- 🧠 **Remembers** every past incident using **Hindsight** persistent memory
- ⚡ **Routes intelligently** to the right model at the right cost using **CascadeFlow**
- 📊 **Explains its decisions** via pipeline logs and audit trails
- 🔄 **Learns** after every resolved incident — gets smarter with every interaction
- 🐳 **Ships to production** via Docker + GitHub Actions CI/CD

---

## Architecture

```
User submits incident
        ↓
  Intent Analysis
        ↓
  Memory Retrieval  ←── Hindsight (PostgreSQL vector store)
        ↓
  Context Builder
        ↓
  CascadeFlow Router ──→ Complexity Score + Budget Check
        ↓
  Model Selection:
    LOW  complexity → Groq llama-3.1-8b-instant   ($0.00005/1k)
    MED  complexity → Groq llama-3.3-70b-versatile ($0.00059/1k)
    HIGH complexity → GPT-4o                        ($0.005/1k)
    BUDGET EXHAUSTED → Ollama (local, free)
        ↓
  Reasoning Engine
        ↓
  Response Validation
        ↓
  Final Response + Audit Log
        ↓
  Memory Reflection → Store new knowledge
```

---

## Tech Stack

| Layer       | Technology                         |
|-------------|-------------------------------------|
| Frontend    | Next.js 15, React 19, Tailwind CSS  |
| Backend     | FastAPI, Python 3.12, asyncio       |
| Memory      | PostgreSQL + cosine similarity      |
| Cache       | Redis                               |
| Local LLM   | Ollama (llama3.2:3b)                |
| Fast LLM    | Groq (llama-3.1-8b-instant)         |
| Powerful LLM| OpenAI GPT-4o                       |
| DevOps      | Docker, GitHub Actions, Nginx       |

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/your-org/incident-agent.git
cd incident-agent
cp .env.example .env
# Edit .env — add GROQ_API_KEY and/or OPENAI_API_KEY
```

### 2. Run in development

```bash
# Start all services with hot reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Or start in production mode
docker compose up -d
```

### 3. Access the app

| Service   | URL                           |
|-----------|-------------------------------|
| Frontend  | http://localhost:3000         |
| API       | http://localhost:8000         |
| API Docs  | http://localhost:8000/docs    |
| Via Nginx | http://localhost:80           |

### 4. Pull local LLM (optional — for offline routing)

```bash
docker exec incident_ollama ollama pull llama3.2:3b
```

---

## Demo Scenarios

### Scenario 1 — First incident (cold memory)

Submit: *"PostgreSQL connection pool exhausted — 500 errors on API"*

The agent:
1. Checks memory → 0 matches
2. CascadeFlow detects critical keywords → routes to powerful/balanced model
3. Analyzes and returns root cause + fix steps
4. Stores in long-term memory on resolution

### Scenario 2 — Repeat incident (warm memory)

Submit the same incident a week later.

The agent:
1. Checks memory → finds previous resolution with high confidence
2. Banner: *"Agent recalled 1 high-confidence similar incident from memory"*
3. Response generated faster with organizational context
4. Cost: same or lower (memory reduces prompt complexity)

### Scenario 3 — Simple query (cost optimization)

Submit: *"What is the status of the database?"*

CascadeFlow: complexity = 0.1 → routes to fast model → $0.000005

### Scenario 4 — Budget exhausted

When `BUDGET_DAILY_USD` is reached, every request automatically falls back to Ollama (local, free, private). No configuration needed.

---

## Running Tests

```bash
cd backend
pip install -r requirements.txt pytest pytest-asyncio aiosqlite

DATABASE_URL=sqlite+aiosqlite:///./test.db \
  APP_ENV=test \
  python -m pytest tests/ -v --asyncio-mode=auto
```

**14 tests, 0 failures** — covering:
- CascadeFlow routing logic (complexity scoring, budget enforcement)
- Hindsight embedding (normalization, cosine similarity)
- Agent pipeline (demo responses, OOM detection)

---

## CI/CD Pipeline

`.github/workflows/ci-cd.yml` runs on every push to `main`:

```
push to main
     ↓
Backend Tests (pytest + PostgreSQL service container)
     ↓
Frontend Tests (lint + type-check + build)
     ↓
Security Scan (Trivy SARIF → GitHub Security tab)
     ↓
Build & Push Docker images → GitHub Container Registry
     ↓
Deploy via SSH → docker compose pull + up
```

---

## API Reference

### POST /api/v1/incidents
Create and immediately analyze an incident.

```json
{
  "title": "PostgreSQL connection pool exhausted",
  "description": "100 connections hit, API returning 500s",
  "severity": "critical",
  "service": "api-gateway",
  "environment": "production"
}
```

Returns full AI analysis, routing decision, audit log, and memory hits.

### GET /api/v1/incidents
List all incidents with optional filters: `?status=open&severity=critical`

### POST /api/v1/incidents/{id}/resolve
Resolve an incident and commit knowledge to permanent memory.

```json
{
  "resolution_notes": "Increased max_connections to 200 and added pgbouncer",
  "root_cause": "Connection pool exhaustion from long-running queries",
  "lessons": ["Always set idle_in_transaction_session_timeout", "Monitor connection pool utilization"]
}
```

### POST /api/v1/memory/search
Semantic search over organizational memory.

```json
{ "query": "postgres connection errors", "top_k": 5 }
```

### GET /api/v1/incidents/stats/summary
Dashboard statistics.

---

## Memory Categories

| Category       | What's stored                          |
|----------------|----------------------------------------|
| `incident`     | High-level incident record             |
| `root_cause`   | Root cause analysis                    |
| `resolution`   | Step-by-step fix that worked           |
| `reflection`   | Lessons learned                        |
| `infrastructure` | Team-specific infra knowledge        |
| `preference`   | Operational preferences                |
| `policy`       | Business and security policies         |
| `workflow`     | Successful runbooks                    |

---

## Model Routing Tiers

| Tier      | Model                      | Cost/1k tokens | When used                    |
|-----------|----------------------------|----------------|------------------------------|
| LOCAL     | Ollama llama3.2:3b         | Free           | Budget exhausted / offline   |
| FAST      | Groq llama-3.1-8b-instant  | $0.00005       | Simple informational queries |
| BALANCED  | Groq llama-3.3-70b         | $0.00059       | Medium complexity errors     |
| POWERFUL  | GPT-4o                     | $0.005         | Critical production incidents |

---

## Environment Variables

| Variable              | Default         | Description                        |
|-----------------------|-----------------|------------------------------------|
| `GROQ_API_KEY`        | —               | Groq API key (fast + balanced tiers)|
| `OPENAI_API_KEY`      | —               | OpenAI API key (powerful tier)      |
| `BUDGET_DAILY_USD`    | `10.0`          | Daily AI spending limit             |
| `DATABASE_URL`        | postgres://...  | Async PostgreSQL connection string  |
| `REDIS_URL`           | redis://...     | Redis connection string             |
| `OLLAMA_BASE_URL`     | http://ollama.. | Local Ollama endpoint               |

---

## Project Structure

```
incident-agent/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI routers
│   │   ├── core/          # Config, DB, Agent orchestrator
│   │   ├── memory/        # Hindsight memory service
│   │   ├── models/        # SQLAlchemy ORM models
│   │   └── runtime/       # CascadeFlow routing engine
│   ├── tests/             # pytest test suite
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/           # Next.js App Router
│   │   ├── components/    # React components
│   │   └── services/      # API client
│   └── Dockerfile
├── infra/
│   ├── nginx/             # Reverse proxy config
│   └── .github/workflows/ # CI/CD pipeline
├── docker-compose.yml
├── docker-compose.dev.yml
└── .env.example
```

---

## Future Roadmap

- **pgvector** integration for production-grade vector similarity
- **Jira / PagerDuty** webhook integration
- **Kubernetes** Helm chart deployment
- **Multi-tenant** memory namespacing per team
- **Feedback loop** — thumbs up/down to improve routing weights
- **Slack bot** for real-time incident reporting
