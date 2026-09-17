# Cybrain QS — Backend

Python + FastAPI + PostgreSQL. Layered `api → services → repositories`.

## Status

Implemented:

- **Auth + Companies CRUD**, company isolation enforced in the repository layer
- **Local LLM provider layer** — Ollama or any OpenAI-compatible local server
- **Document processing** — PDF/DOCX extraction, structure preservation,
  scanned-document detection, structure-based chunking

Partially implemented: pgvector retrieval infrastructure and the
KnowledgeObject model. Not yet built: the complete retrieval API, CKM
extraction/verification workflow and SOP backend/generation lifecycle. The
frontend is wired to auth, company and document APIs. See
`../docs/PROJECT_STATE.md`.

## AI is switched off

`AI_FEATURES_ENABLED=false`. The core application — auth, companies, document
upload and parsing, dashboards — runs with **no inference server of any kind**.

Nothing was deleted. While the flag is off:

| Area | Behaviour |
| --- | --- |
| Document upload, parsing, chunking | works normally, no model involved |
| Embedding | skipped; chunks stored with `embedding = NULL` |
| Retrieval / RAG / extraction / generation | routers not registered; services idle |

`app/integrations/llm/`, `app/modules/knowledge/retrieval.py` and the embedding
path in `app/modules/documents/ingestion.py` are intact. To enable them, set
`AI_FEATURES_ENABLED=true`, point `LLM_BASE_URL` at a running endpoint, register
the AI routers in `app/api/v1/router.py` behind `require_ai_enabled`, and
re-ingest to backfill vectors.

## Local LLM (when re-enabled)

**No cloud provider, no API key.** Point the backend at whatever you run
locally. With Ollama:

```bash
ollama pull llama3.1:8b        # chat model
ollama pull nomic-embed-text   # embeddings, 768 dimensions
```

To use LM Studio, vLLM, llama.cpp or LocalAI instead, set `LLM_PROVIDER=openai_compatible`
and point `LLM_BASE_URL` at its `/v1` endpoint. Changing model or runtime is a
configuration change only — see `.env.example` and ADR-0012.

## Run it

```bash
cd backend
docker compose up -d                              # Postgres 16 + pgvector on :5432
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
cp .env.example .env                              # then set SECRET_KEY
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

Interactive API docs: <http://localhost:8000/docs>

## Verify it

```bash
.venv/Scripts/python -m pytest        # no server or LLM needed
```

Tests run in-process against a dedicated `*_test` database, each inside a
transaction that is rolled back, so they are isolated and CI-ready.

Only when `AI_FEATURES_ENABLED=true` and an endpoint is running:

```bash
.venv/Scripts/python scripts/check_llm.py   # probes endpoint, measures embedding size
.venv/Scripts/python scripts/test_rag.py    # embeddings, retrieval, tiers, isolation
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for structure, layer responsibilities
and the pre-production checklist.

## Layout

```
app/
├── main.py             app factory, middleware and error handlers
├── core/               config, database, security, logging and errors
├── modules/            auth, companies, documents and knowledge domains
├── integrations/llm/   local provider protocol + adapters
├── processing/         PDF/DOCX extraction and structure-aware chunking
├── shared/             shared models, schemas, enums and registry
└── api/v1/             router aggregation
```

## Endpoints

| Method | Path | Auth |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | no |
| POST | `/api/v1/auth/login` | no |
| GET | `/api/v1/auth/me` | yes |
| GET | `/api/v1/companies` | yes |
| POST | `/api/v1/companies` | yes |
| GET | `/api/v1/companies/{id}` | yes |
| PATCH | `/api/v1/companies/{id}` | yes |
| DELETE | `/api/v1/companies/{id}` | yes |
| POST | `/api/v1/companies/{id}/documents` | yes |
| GET | `/api/v1/companies/{id}/documents` | yes |
| GET | `/api/v1/companies/{id}/documents/{document_id}` | yes |
| GET | `/api/v1/companies/{id}/documents/{document_id}/chunks` | yes |
| DELETE | `/api/v1/companies/{id}/documents/{document_id}` | yes |
| GET | `/api/v1/companies/{id}/stats` | yes |
| GET | `/health` | no |
| GET | `/health/ready` | no |

## Rules this code enforces

- **Company isolation is a repository concern.** Every company read joins
  `user_company_access` for the requesting user. A handler cannot forget it.
- **Unknown and forbidden both return 404**, so the API cannot be used to probe
  whether another tenant's company exists.
- **Login failures are indistinguishable** whether the email exists or not.
- **Secrets never enter the repository.** `.env` is git-ignored; `.env.example`
  carries no real values.
