# Project State

This is the repository snapshot today. **Working code is the source of truth.**
If this file and the implementation disagree, inspect the implementation and
update this file with the relevant change.

## Progress overview (kitna hua / kitna baqi)

Rough product completion by major area. Percentages are judgment calls for
planning, not formal metrics.

| Area | Status | ~Done | Remaining work |
| --- | --- | ---: | --- |
| Frontend shell, i18n, auth UI | Implemented | 85% | Design-backed screens for placeholder nav routes |
| Companies CRUD + detail | Implemented | 90% | Role-based action gating in UI |
| Company onboarding UI | Partial | 60% | Full CKM-building path; auto KO extraction from onboarding |
| Documents upload + processing | Implemented | 75% | Durable file storage, OCR, background jobs |
| Auth (JWT) | Implemented | 80% | Refresh/revocation; role enforcement |
| Knowledge Objects API | Partial | 55% | Provenance-complete review UX; richer verification audit |
| pgvector retrieval | Partial | 40% | Public retrieval API + end-to-end UI |
| Local LLM adapters | Implemented | 70% | Production model/embed-dim decisions |
| CKM management product | Partial | 35% | Full lifecycle, tiers UX, isolation proofs in product flows |
| SOP wizard | Partial | 15% | Steps 02–06, Blueprint, mapping, editor |
| SOP backend + generation | Missing | 5% | Models, APIs, grounded draft pipeline |
| SOP approval / versioning | Missing | 0% | Review, approve, immutable versions |
| Frontend automated tests | Missing | 0% | Test runner + coverage for critical flows |
| Ops (jobs, storage, deploy) | Missing | 10% | Job runner, file store, OCR, deploy config |

**Overall (product MVP toward regulated SOP+CKM):** roughly **~40%** foundation in
place (platform, companies, documents, early knowledge); **~60%** still to build
(full CKM productization, retrieval UX, entire SOP lifecycle).

### Already solid (do not rebuild)

- App platform: FastAPI + React/Vite, company isolation pattern, JWT login
- Document pipeline: PDF/DOCX extract → chunk → persist (optional embeddings)
- Early knowledge: extract / list / edit / confirm / reject APIs
- Local AI plumbing: Ollama / OpenAI-compatible adapters

### Still the bulk of the product

- End-to-end CKM as a managed, auditable knowledge base in the UI
- Public retrieval + grounded SOP generation
- Full six-step SOP wizard, approval gate, version history
- Background processing, OCR, durable source files

---

## Implemented

### Frontend

- React 19, TypeScript and Vite; English/German localisation (`en` / `de`).
- JWT login/registration/current-user lookup and protected routes.
- FastAPI clients for companies, authentication, documents and knowledge.
- Company list/search/create/edit/delete/detail, document interaction and stats.
- Company onboarding UI with persisted profile answers, idempotent create,
  staged document/template upload, local draft restore.
- SOP wizard **step 01** (project initialization) implemented.
- Placeholder routes for screens without an approved design (SOP library,
  workflows, knowledge, assistant, records, alerts, settings, help).

### Backend and data

- FastAPI app factory, injected configuration, middleware, request IDs,
  logging, security headers, CORS and typed errors.
- PostgreSQL via SQLAlchemy and Alembic migrations; pgvector for embeddings.
- JWT auth, login rate limiting and repository-scoped user/company access.
- Company CRUD and PDF/DOCX upload, extraction, scanned-document detection,
  structure-aware chunking and document/chunk persistence.
- Local LLM abstraction for Ollama and OpenAI-compatible local runtimes.
- Optional embedding during ingestion (off unless AI is enabled/configured).
- Company-prefiltered pgvector **retrieval infrastructure** (service layer)
  that preserves tier and source location.
- `KnowledgeObject` model plus company-scoped APIs:
  extract from chunks, list, edit label, confirm, reject, cancel extract op.
- Backend tests for auth, companies, tenant isolation, documents, processing
  and knowledge-related coverage where present.

### Repo / tooling (environment)

- Root `.gitignore` and `.cursorignore`.
- GitHub remote: https://github.com/Arshiyan-Elahi/Cybrain-Qs-New (`main`, public).

---

## Partially implemented

- **Retrieval:** infrastructure exists; **no registered public retrieval/search
  API** and no end-to-end retrieval UI.
- **Embeddings:** require `AI_FEATURES_ENABLED` and a configured local endpoint.
- **Knowledge / CKM:** extract + human confirm/reject exist; full
  provenance-complete review UX, CKM management product and tier presentation
  in all flows are incomplete. Onboarding is **not** yet a complete
  CKM-building workflow (no automatic KO extraction wired as the onboarding
  outcome).
- **SOP wizard:** step 01 only; steps 02–06 are placeholders.
- **Roles:** `UserCompanyAccess.role` is stored but does not yet gate actions.

---

## Not yet implemented

- Full CKM product: managed knowledge base UI, complete verification audit
  trail presentation, tier-aware authoring surfaces.
- Registered retrieval API and retrieval/assistant UI.
- SOP backend: Blueprint, Knowledge Mapping, grounded generation pipeline.
- SOP review, approval and immutable version lifecycle.
- Remaining SOP wizard steps and complete editor/library workflows.
- Background job runner, durable source-file storage and OCR engine.
- Frontend automated test suite.

---

## Current technical debt / known issues

- `UserCompanyAccess.role` is stored but not enforced as authorisation.
- Uploaded source bytes are not retained after parsing.
- Parsing/ingestion currently runs during the upload request (no job queue).
- Token revocation/refresh is not implemented.
- OCR need is detected and surfaced, but OCR is not integrated.
- Deployment must settle local models, embedding dimensions, file storage and
  background jobs.
- Frontend automated tests are not configured; use build, lint and browser QA.

---

## Runtime expectations

- PostgreSQL with pgvector is required for backend operation and integration
  tests; `backend/docker-compose.yml` supplies it locally.
- The core app runs without inference while `AI_FEATURES_ENABLED=false`.
- AI uses a configured local Ollama or OpenAI-compatible endpoint. No cloud
  Anthropic credential is required for the implemented path.

---

## Suggested next priorities (when building again)

1. Close knowledge loop in UI (review/confirm proposed KOs with provenance).
2. Public retrieval API + thin UI, still company-scoped and tier-labelled.
3. SOP wizard steps 02+ only against approved designs; no invented screens.
4. Background jobs + durable files before heavy ingestion/OCR work.

_Last reconciled with the repository: 2026-09-17._
