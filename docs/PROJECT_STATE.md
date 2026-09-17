# Project State

This is the repository snapshot today. **Working code is the source of truth.**
If this file and the implementation disagree, inspect the implementation and
update this file with the relevant change.

## Implemented

### Frontend

- React 19, TypeScript 6 and Vite 8; English/German localisation.
- JWT login/registration/current-user lookup and protected routes.
- FastAPI integration for companies, authentication and documents.
- Company list/search/create/edit/delete/detail, document interaction and stats.
- Company onboarding UI with persisted profile answers, idempotent create,
  staged document/template upload, local draft restore, SOP wizard step 01,
  and placeholder routes for screens without an approved design.

### Backend and data

- FastAPI app factory, injected configuration, middleware, request IDs,
  logging, security headers, CORS and typed errors.
- PostgreSQL via SQLAlchemy and Alembic migrations.
- JWT auth, login rate limiting and repository-scoped user/company access.
- Company CRUD and PDF/DOCX upload, extraction, scanned-document detection,
  structure-aware chunking and document/chunk persistence.
- Local LLM abstraction for Ollama and OpenAI-compatible local runtimes.
- Optional embedding during ingestion, disabled by default.
- Company-prefiltered pgvector retrieval infrastructure that preserves tier
  and source location, plus a `KnowledgeObject` database model.
- Backend tests for auth, companies, tenant isolation, documents and processing.

## Partially implemented

- Retrieval exists as infrastructure but has no registered public API.
- Embeddings require local AI to be enabled and configured.
- Knowledge Object persistence exists; creation, provenance-complete review,
  verification APIs and CKM management do not.
- Company onboarding is not a complete CKM-building workflow (no automatic
  Knowledge Object extraction from onboarding).
- SOP wizard step 01 exists; steps 02–06 are placeholders.
- Company membership is enforced, but stored roles do not yet control actions.

## Not yet implemented

- Full Knowledge Object extraction/review/verification and CKM management.
- Registered retrieval API and end-to-end retrieval UI.
- SOP backend, Blueprint, Knowledge Mapping and grounded generation.
- SOP review, approval and immutable version lifecycle.
- Remaining SOP wizard steps and complete editor/library workflows.
- Background job runner, durable source-file storage and OCR engine.

## Current technical debt / known issues

- `UserCompanyAccess.role` is stored but not enforced as authorisation.
- Uploaded source bytes are not retained after parsing.
- Parsing/ingestion currently runs during the upload request.
- Token revocation/refresh is not implemented.
- OCR need is detected and surfaced, but OCR is not integrated.
- Deployment must settle local models, embedding dimensions, file storage and
  background jobs.
- Frontend automated tests are not configured; use build, lint and browser QA.

## Runtime expectations

- PostgreSQL with pgvector is required for backend operation and integration
  tests; `backend/docker-compose.yml` supplies it locally.
- The core app runs without inference while `AI_FEATURES_ENABLED=false`.
- AI uses a configured local Ollama or OpenAI-compatible endpoint. No Anthropic
  credential is required.

_Last reconciled with the repository: 2026-09-11._
