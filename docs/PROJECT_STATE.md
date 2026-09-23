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
| Company onboarding UI | Partial | 75% | Dedicated CKM page polish beyond company create |
| Documents upload + processing | Implemented | 82% | Durable file storage, production OCR engine wiring, background jobs |
| Auth (JWT) | Implemented | 80% | Refresh/revocation; role enforcement |
| Knowledge Objects API | Implemented | 85% | Dedicated `/knowledge` product page; richer history UI |
| pgvector retrieval | Partial | 62% | Product retrieval UI; SOP generator as consumer |

| Local LLM adapters | Implemented | 70% | Production model/embed-dim decisions |
| CKM management product | Partial | 70% | Standalone CKM route; tier presentation polish |
| SOP wizard | Partial | 50% | Prose generation; approval/version UI; design-PDF polish |
| SOP backend + generation | Partial | 25% | Grounded draft pipeline; approval/versioning |
| SOP approval / versioning | Missing | 0% | Review, approve, immutable versions |
| Frontend automated tests | Missing | 0% | Test runner + coverage for critical flows |
| Ops (jobs, storage, deploy) | Missing | 10% | Job runner, file store, OCR, deploy config |

**Overall (product MVP toward regulated SOP+CKM):** roughly **~48%** foundation in
place (platform, companies, documents, CKM review loop); **~52%** still to build
(retrieval UX, entire SOP lifecycle, ops).

### Already solid (do not rebuild)

- App platform: FastAPI + React/Vite, company isolation pattern, JWT login
- Document pipeline: PDF/DOCX extract → chunk → persist (optional embeddings)
- CKM review loop: onboarding → proposed KOs; document extract → proposed;
  confirm / edit / reject with provenance, history and company isolation
- Local AI plumbing: Ollama / OpenAI-compatible adapters

### Still the bulk of the product

- Dedicated Knowledge / CKM product route (beyond company-detail panel)
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
- Company Documents/SOP list: permanent delete with confirmation and verified-
  dependency blocked modal; list/count/CKM refresh without full page reload.
- Company Profile header: owner-gated permanent company delete (3-dot menu +
  typed-name confirmation); list selection updates without reload.
- Company onboarding UI with persisted profile answers, idempotent create,
  staged document/template upload, local draft restore.
- SOP wizard is a **4-step guided Create SOP** flow (title → prepare → check →
  document draft) over create-project / build-blueprint / mark-ready APIs.
  No SOP prose generator yet; draft body uses mapped verified knowledge and
  keeps blocked sections blocked.
- Everyday navigation is Companies, Company Knowledge, Create SOP, SOPs and
  Settings. Company Knowledge is a guided review experience (summary counts,
  plain-language groups, Accept/Edit/Reject) over the existing KO confirm/
  edit/reject APIs; SOPs remain a plain-language entry to the wizard. Workflows, assistant, records, alerts and
  help stay reachable from Settings.

### Backend and data

- FastAPI app factory, injected configuration, middleware, request IDs
  (`req_…`), structured console/JSON logging (HTTP, routing, embeddings,
  retrieval, ingestion, CKM), security headers, CORS and typed errors.
- PostgreSQL via SQLAlchemy and Alembic migrations; pgvector for embeddings.
- JWT auth, login rate limiting and repository-scoped user/company access.
- Company CRUD and PDF/DOCX upload, layout-aware extraction (DOCX multi-signal,
  Docling-or-pypdf PDF), digital/mixed/scanned classification, pluggable OCR
  provider interface, structure normalization, extraction QA gate, structure-
  aware chunking and document/chunk persistence.
- Tenant-scoped document DELETE: cancels in-flight ingestion, clears pgvector
  embeddings then chunks, strips multi-source proposed CKM evidence, deletes
  single-source proposed/rejected document-derived KOs, blocks verified/
  superseded dependencies with structured 409, syncs `sop_count`, structured
  delete audit events (`document_delete_*`).
- Company DELETE (owner role only): cancels company document ops, deletes all
  company-owned documents/chunks/embeddings, all CKM objects+history (verified
  included), onboarding/regulations/access rows; structured `company_delete_*`
  logs; does not delete the user account or other tenants.
- Local LLM abstraction for Ollama and OpenAI-compatible local runtimes, with
  automatic AI routing (`AI_ROUTING_MODE=auto|remote|fallback`): remote LLM/
  embeddings when healthy; `fallback` forces Gemini LLM + local Nomic 768-d
  embeddings without the auto-mode compatibility gate; auto mode keeps the
  compat self-test before remote→local failover. `POST .../documents/{id}/
  embeddings` retries NULL vectors on existing chunks.
- Optional embedding during ingestion (off unless AI is enabled/configured).
- Company-prefiltered pgvector **retrieval infrastructure** (service layer)
  that preserves tier and source location.
- Verified CKM **generation-context** package: trusted Knowledge Objects
  (`status=verified` only; proposed/rejected/superseded excluded), grouped by
  type with provenance, plus semantic document chunks via `RetrievalService`.
  Development preview: `POST /api/v1/companies/{id}/retrieval/preview`
  (404 in production; does not draft SOP text).
- `KnowledgeObject` model plus company-scoped APIs: extract from chunks,
  propose from onboarding, filtered list, history, edit, confirm, reject.
- Provenance `source_kind`: onboarding | uploaded_document | human_created |
  ai_extracted; append-only `knowledge_object_history`; verified edits
  supersede without destroying evidence.
- Company create/update with onboarding auto-proposes Knowledge Objects.
- SOP **projects** persist title/topic/status/blueprint JSONB; company-scoped
  APIs create a project, build/rebuild a Blueprint from verified CKM + chunks,
  and mark `generation_ready`. No SOP prose is generated.

### Repo / tooling (environment)

- Root `.gitignore` and `.cursorignore`.
- GitHub remote: https://github.com/Arshiyan-Elahi/Cybrain-Qs-New (`main`, public).

---

## Partially implemented

- **Retrieval:** company-prefiltered chunk `RetrievalService` plus verified-CKM
  `GenerationContextService` and a non-production preview endpoint. No product
  retrieval UI and no SOP generator consuming the package yet.
- **Embeddings:** require `AI_FEATURES_ENABLED` and a configured local endpoint.
- **Knowledge / CKM:** onboarding→proposed KOs, document extract, confirm /
  edit / reject, provenance kinds, history API and company-detail review UI
  exist. Dedicated `/knowledge` route is still a placeholder; history is API-
  first (panel shows confirmation metadata, not a full timeline UI).
- **SOP wizard:** step 01 designed; steps 02–04 show a functional Blueprint
  review; steps 05–06 remain placeholders.
- **SOP backend:** project + Blueprint mapping exist; grounded draft generation
  does not.
- **Roles:** `UserCompanyAccess.role` is stored; company permanent delete
  requires `owner`. Other actions are not yet role-gated.

---

## Not yet implemented

- Dedicated CKM / Knowledge product page (beyond company-detail panel).
- Retrieval/assistant UI. SOP generation does not yet consume the context package.
- SOP backend: grounded generation pipeline (Blueprint exists).
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
- OCR need is detected and classified (digital/mixed/scanned); a pluggable OCR
  provider interface exists (`NullOcrProvider` by default). Production engines
  (Docling OCR, Tesseract/ocrmypdf) are not bundled.
- Docling is optional for layout-aware PDF; pypdf remains the default fallback.
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

_Last reconciled with the repository: 2026-09-18._
