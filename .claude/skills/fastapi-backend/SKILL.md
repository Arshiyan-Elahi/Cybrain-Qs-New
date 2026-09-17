---
name: fastapi-backend
description: Python + FastAPI conventions for the implemented Cybrain QS backend — domain modules, layering, company scoping, Pydantic boundaries, processing, retrieval and local LLM integration.
---

# FastAPI backend

> **Current state.** Inspect `docs/PROJECT_STATE.md` and the code. Auth,
> companies, documents, persistence and tests exist; CKM/SOP workflows and a
> public retrieval API are incomplete.

## Layering

```
backend/app/
├── main.py              app factory and router registration
├── api/v1/              router aggregation
├── modules/             auth, companies, documents and knowledge
├── processing/          parsing, extraction and chunking
├── integrations/llm/    local inference protocol and adapters
├── shared/              shared models, schemas and enums
└── core/                config, database, logging, errors and dependencies
```

Direction of dependency is one-way: `api → services → repositories`. A router
never touches the database. A service never builds an HTTP response. Processing,
retrieval and generation are called *by* services, never from a router
(`CLAUDE.md` §3).

## Non-negotiables

- **Company scope is a repository-level concern.** Resolve the company from the
  request once, pass it down, and apply it inside the repository so a forgotten
  filter in a handler cannot leak another company's data. Never rely on the
  caller to remember.
- **Provenance is written on the same path that creates knowledge.** No
  create-now-attribute-later. If provenance cannot be determined, the write does
  not happen.
- **Extraction and generation results are persisted as `proposed`.** There is no
  code path, confidence threshold or bulk flag that writes `verified` without an
  explicit human verification action.
- **Knowledge tier travels with the data** through retrieval, prompt and
  response. Never flatten Company / Industry / Global into one undifferentiated
  set.

## Conventions

- Pydantic models define the API boundary; they are not reused as database
  models. Separate schemas for request and response.
- The current SQLAlchemy session is synchronous. Keep blocking persistence and
  parsing out of `async` handlers; move ingestion/extraction/embedding to the
  future background runner rather than introducing mixed sync/async behavior.
- Long-running work should be queued. The current upload path is synchronous
  technical debt, not the target pattern.
- Errors are typed domain errors mapped to HTTP status in one place in
  `core/`, not `HTTPException` scattered through services.
- Configuration through environment variables via a settings object. **No
  secrets, API keys or connection strings committed to the repository.**

## API contract with the frontend

The frontend calls the backend through `frontend/src/services/`; those modules,
`frontend/src/types/` and existing Pydantic schemas form the live contract.

## Do not use this skill for

- Frontend work — that is `react-frontend`.
- Schema and migration design — that is `postgres-database`.
- Retrieval and prompt design — those are `rag-retrieval` and `llm-generation`.

## See also

`docs/ARCHITECTURE.md`, `docs/DOMAIN_MODEL.md`, `docs/DECISIONS.md` ADR-0001,
`backend/README.md`.
