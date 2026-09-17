# Architecture

This describes the current implementation. See `PROJECT_STATE.md` for gaps.
Working code is authoritative if documentation differs.

## System shape

```text
React + TypeScript + Vite
          │ HTTP/JSON + JWT
          ▼
FastAPI routers → services → repositories
          │                    │
          │                    ▼
          │          PostgreSQL + pgvector
          │          SQLAlchemy + Alembic
          ▼
Document processing / retrieval / local inference adapters
```

## Frontend

The React app uses `react-router-dom`, CSS Modules, i18next and typed service
modules. `AuthProvider` manages the JWT session, `RequireAuth` protects routes,
and `src/services/` is the HTTP boundary.

`components/` contains reusable UI, `features/` domain UI, `pages/` route
composition, `services/` API clients, `data/` remaining local/mock content,
`i18n/` translations, and `types/` shared frontend/API shapes. Company screens
use live backend data. SOP suggestions and unfinished wizard areas remain local
or placeholders. Approved PDF designs remain the visual source of truth.

## Backend

FastAPI is built through an application factory with injected settings,
request IDs, logging, security headers, explicit CORS, gzip and typed errors.

```text
backend/app/
├── main.py
├── api/v1/                 router aggregation
├── core/                   config, DB, security, middleware, errors
├── modules/
│   ├── auth/               router/service/repository/models/schemas
│   ├── companies/          router/service/repository/models/schemas
│   ├── documents/          upload, persistence and ingestion
│   └── knowledge/          KnowledgeObject model and retrieval service
├── processing/             PDF/DOCX extraction and chunking
├── integrations/llm/       local provider protocol and adapters
└── shared/                 common models, schemas, enums and registry
```

Dependency direction is router → service → repository. FastAPI dependencies
construct the objects and request transactions are managed centrally.

## Database and isolation

PostgreSQL is the only primary datastore. SQLAlchemy defines models and Alembic
owns migrations. Stable/queryable metadata is relational, JSONB holds
variable-shaped payloads and pgvector holds embeddings.

Company visibility is enforced through `user_company_access` inside repository
queries. Unknown and inaccessible companies both return not-found behavior.
Roles are stored but role-based permissions remain incomplete.

## Documents

```text
upload → validate → PDF/DOCX extraction → structure-aware chunks → persist
                                                        └→ optional embedding
```

Extraction preserves document structure and location. Scanned files are marked
as needing OCR. Source bytes are not retained after parsing, and ingestion still
runs in the request path; both are tracked debt.

## Local inference and retrieval

AI uses a provider protocol with Ollama and OpenAI-compatible local adapters.
There is no active cloud-Anthropic architecture. AI is disabled by default, so
auth/company/document features run without an inference server.

Retrieval embeds a query and applies company, tier and non-null-vector filters
before pgvector distance ordering. Results carry tier and source provenance.
This infrastructure exists but is not registered as a complete public API; the
CKM and SOP generation workflows are not implemented.

## Capability status

| Capability | State |
| --- | --- |
| Company profiles/access | Implemented |
| Document upload/extraction/chunks | Implemented |
| Optional embeddings/retrieval service | Partial; infrastructure only |
| KnowledgeObject model | Partial; workflow/API missing |
| Human knowledge verification and CKM management | Not implemented |
| SOP wizard step 01 | Implemented frontend |
| Blueprint, mapping and grounded generation | Not implemented |
| SOP review, approval and immutable versions | Not implemented |

## Cross-cutting invariants

Company isolation, proposed-first AI output, explicit human verification,
complete provenance, persistent knowledge tiers, immutable approved history and
visible knowledge gaps apply to every new subsystem.
