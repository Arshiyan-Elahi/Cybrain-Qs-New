# Backend architecture

FastAPI + PostgreSQL, organised by **domain module** rather than technical type.

## 1. Folder structure

```
backend/
├── app/
│   ├── main.py                    application factory: middleware, handlers, routers
│   │
│   ├── core/                      platform concerns, no business logic
│   │   ├── config.py              typed settings, fail-fast validation
│   │   ├── database.py            lazy engine, session = transaction boundary
│   │   ├── dependencies.py        shared DI aliases (DbSession, AppSettings)
│   │   ├── errors.py              domain error taxonomy -> HTTP status
│   │   ├── exception_handlers.py  one error response shape for the whole API
│   │   ├── logging.py             structured logging + request-id context
│   │   ├── middleware.py          request context, security headers
│   │   ├── pagination.py          PageParams / Page envelope
│   │   ├── rate_limit.py          sliding-window limiter
│   │   └── security.py            password hashing, JWT encode/decode
│   │
│   ├── shared/                    cross-module primitives
│   │   ├── models.py              declarative Base, UUID + timestamp mixins
│   │   ├── schemas.py             CamelModel base (API speaks camelCase)
│   │   ├── enums.py               KnowledgeTier, KnowledgeStatus, DocumentStatus
│   │   └── registry.py            imports every model so mappers resolve
│   │
│   ├── modules/                   one folder per business capability
│   │   ├── auth/
│   │   │   ├── router.py          HTTP surface
│   │   │   ├── dependencies.py    DI wiring + CurrentUser
│   │   │   ├── service.py         business rules
│   │   │   ├── repository.py      data access
│   │   │   ├── models.py          User, UserCompanyAccess
│   │   │   └── schemas.py         request/response contracts
│   │   ├── companies/             (same six files)
│   │   ├── documents/             + ingestion.py (parse -> chunk -> store)
│   │   └── knowledge/             models + retrieval (inactive: AI disabled)
│   │
│   ├── integrations/llm/          provider protocol + ollama / openai_compatible
│   ├── processing/                pure PDF/DOCX extraction and chunking
│   └── api/v1/router.py           aggregates module routers under one prefix
│
├── alembic/                       migrations
├── tests/                         pytest: conftest + one file per module
├── scripts/                       operational scripts needing a live endpoint
├── docker-compose.yml             Postgres 16 + pgvector
└── pyproject.toml                 pytest + ruff config
```

## 2. Why each layer exists

| Layer | Responsibility | Must not |
| --- | --- | --- |
| **Router** | Translate HTTP to a service call. Declare status codes and response models. | Contain business rules or touch the database |
| **Service** | Business rules, authorisation decisions, orchestration across repositories | Import `fastapi`, build HTTP responses, or commit |
| **Repository** | Query construction and data access. **Company scoping lives here** | Contain business rules |
| **Models** | Persistence shape and database-level invariants (CHECK constraints) | Be reused as API contracts |
| **Schemas** | The API contract, validated at the boundary | Be reused as ORM models |
| **Dependencies** | Wire the above together for FastAPI | Contain logic |
| **core/** | Cross-cutting platform code | Know about any specific domain |

The rule that keeps this honest: **a service never imports `fastapi`.** That is
what makes business logic testable without a web framework and reusable from a
background worker later.

Grouping by domain rather than type means a change to "documents" touches one
folder instead of five, and a module can be extracted into its own service
later by moving a directory.

## 3. Major architectural decisions

### The request is the transaction boundary
`get_db()` commits when the handler returns and rolls back on any exception.
Services call `flush()` (to get generated ids) but never `commit()`. Previously
8 scattered commits meant a multi-step operation could half-commit.

### Dependency injection via FastAPI `Depends`
Services receive their repositories; routers receive services. No component
constructs its own collaborators, so tests substitute a fake by overriding one
provider. No third-party DI container — FastAPI's own mechanism is sufficient
and adding one would be over-engineering.

### Errors are domain types, mapped once
Services raise `NotFoundError`, `ConflictError`, `ValidationError`. Exactly one
module converts them to HTTP with a consistent body:

```json
{ "error": { "code": "not_found", "message": "..." }, "requestId": "..." }
```

### Application factory
`create_app(settings)` rather than a module-level singleton, so tests build an
isolated instance against a different database, and configuration is never read
at import time.

### camelCase at the boundary
A Pydantic alias generator serialises camelCase so the TypeScript client needs
no mapping layer, while Python stays snake_case. Requests accept both.

### Paged list responses
Every list endpoint returns `{items, total, limit, offset}` with `limit`
clamped server-side. Unbounded lists are a latent outage.

## 4. Security and scalability improvements

**Security**

| Change | Why |
| --- | --- |
| Production config validation | A deploy missing `SECRET_KEY` now fails at start-up instead of running with a key published in this repository |
| Login rate limiting | Sliding window per email+IP; a success resets it, so real users are never penalised |
| CORS narrowed | Explicit methods and headers; `*` with `allow_credentials` was unsafe |
| Security headers | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, HSTS in production |
| Docs disabled in production | No schema explorer on a public deployment |
| Database errors sanitised | Driver messages can leak schema; logged, not returned |
| Upload type checked before parsing | Untrusted bytes never reach the parser on an obviously wrong type |
| 404 instead of 403 | A 403 would confirm another tenant's resource exists |
| Identical login failure messages | The endpoint cannot be used to enumerate accounts |

**Scalability**

| Change | Why |
| --- | --- |
| Connection pooling configured | `pool_size`, `max_overflow`, `pool_recycle`, `pool_pre_ping` — survives database restarts and idle timeouts |
| Parsing moved to a threadpool | A 25 MB parse no longer stalls the event loop for every other request |
| Pagination everywhere | Response size is bounded regardless of tenant size |
| Lazy engine construction | Importing a model no longer opens a connection |
| Gzip responses | Cheap bandwidth win on JSON lists |
| Request-id tracing | A slow or failing request can be found in logs across services |

## 5. Before production deployment

Ordered by risk. None of these are done.

1. **Move rate limiting to Redis.** The current limiter is per-process; behind
   more than one worker each keeps its own counter.
2. **Background job runner** (Celery/RQ/arq). Document parsing still happens
   inside the upload request. It belongs in a queue with a status the UI polls.
3. **Token revocation and refresh.** No `jti`, no deny-list, no refresh token —
   a leaked token is valid until it expires.
4. **Enforce roles.** `UserCompanyAccess.role` is stored and never read; every
   member is effectively an owner.
5. **Retain uploaded bytes** in object storage. They are discarded after
   parsing, so a document can never be re-processed or re-embedded from source.
6. **Secrets manager** instead of `.env` on disk.
7. **CI pipeline** running `pytest` and `ruff` on every push.
8. **Metrics and tracing** — Prometheus counters, OpenTelemetry spans. Logging
   alone will not answer "why is p99 slow".
9. **Caching layer.** Not yet warranted; add Redis for company/stats reads when
   a real hot path is measured rather than guessed.
10. **Database hardening** — read replica, PITR backups with a tested restore,
    and a decision on row-level security as defence in depth.
11. **Load testing** to size the pool and worker count.
12. **Alembic in the deploy pipeline**, gated so migrations run before rollout.
