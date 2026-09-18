# Decisions

Architectural decisions and their reasoning. Newest first. Each entry is
**Accepted**, **Proposed** or **Superseded**.

Add an entry when a choice constrains future work. Do not rewrite history —
supersede instead.

---

## ADR-0010 — Company isolation via repository scoping; JWT bearer auth

**Status:** Accepted · 2026-08-12 · resolves the "Tenant isolation" open question

**Company is the isolation boundary.** A user reaches company data only through
a `user_company_access` row, and that filter is applied inside
`CompanyRepository`, not in routers — so a handler cannot forget it and leak
another tenant's data.

Chosen over PostgreSQL row-level security for now: simpler local development,
easier to test, and portable. RLS remains available as defence in depth if a
customer audit demands it; that would be a new ADR, not a rewrite, because the
`company_id` columns and access table are already in place.

Two consequences worth stating:

- **Unknown and forbidden both return 404.** A 403 would confirm that another
  tenant's company exists, which is itself a leak.
- **Login failures are indistinguishable** whether or not the email exists, so
  the endpoint cannot be used to enumerate accounts.

Auth is email/password with a bcrypt hash and a signed JWT bearer token.
`SECRET_KEY` comes from the environment and has no usable default.

---

## ADR-0012 — Local LLM only; modular provider behind one protocol

**Status:** Accepted · 2026-08-12 · supersedes ADR-0011

All inference runs on a locally hosted model. **No cloud AI provider and no API
key.** For a product handling regulated customers' private documents, keeping
inference on infrastructure the customer controls is also the stronger position
on company-knowledge isolation (CLAUDE.md §4).

`app/integrations/llm/` defines a single `LLMProvider` protocol — `health()`, `complete()`,
`embed()` — with two implementations:

| Provider | Targets |
| --- | --- |
| `ollama` | Ollama's native API. Batch embeddings, reports the model back. |
| `openai_compatible` | LM Studio, vLLM, llama.cpp server, LocalAI, Ollama's `/v1`. |

Changing runtime or model is configuration only (`LLM_PROVIDER`,
`LLM_BASE_URL`, `LLM_CHAT_MODEL`, `LLM_EMBEDDING_MODEL`). No service, router or
migration imports a concrete provider, so a third runtime is a new file plus a
registry entry.

**Consequences**

- `Completion` carries `model` and `provider`, because anything derived from a
  model must be traceable to the exact model that produced it.
- `LLM_EMBEDDING_DIMENSIONS` fixes the pgvector column width. Changing the
  embedding model means a migration and a full re-embed, never a mixed index.
- Nothing in the request path calls a model; generation and extraction are
  queued work.

---

## ADR-0011 — Anthropic Claude for extraction and generation

**Status:** Superseded by ADR-0012 · 2026-08-12

Chosen initially to match the `claude-api` skill. Withdrawn before any code was
written against it: the project owner requires local inference, so no cloud
provider dependency exists anywhere in the codebase.

---

## ADR-0009 — i18n with i18next + react-i18next; English is the default

**Status:** Accepted · 2026-08-12 · resolves the "i18n" open question

The UI was hardcoded in German. It is now fully translatable, with **English as
the default language** and German switchable at runtime.

- **`i18next` + `react-i18next`** — the standard, lightweight choice. No language
  detector package: the stored preference is read directly from `localStorage`
  in `src/i18n/index.ts`, which is a few lines and avoids a third dependency.
- **Strings live in `src/i18n/en.json` and `de.json`**, never inline in
  components. Components reference keys only.
- **Language-dependent mock data is stored as keys, not display strings.**
  `Company.industryKey`, `locationKey`, `primaryLanguageKey`, `regulationIds`,
  and the wizard's `labelKey` fields resolve through `t()` at render time, so one
  dataset serves both languages. CKM figures are stored as numbers and
  interpolated into a translated sentence.
- **Dates are stored as ISO `YYYY-MM-DD`** and formatted per locale by
  `utils/formatDate`. German renders `15.05.2025`, matching the design exactly;
  English renders `15/05/2025` (`en-GB`, day-first, matching the European market
  the product targets).
- **Language preference persistence is browser-local** — `localStorage` key
  `cybrain-qs.language`; the backend does not currently store it.

**Consequence:** new user-facing text must be added as a key in both JSON files.
A string literal rendered directly in a component is now a defect.

**Note:** the German design draws the wizard footer button as "Search Similar
Content" in English. It is reproduced as drawn per ADR-0006, so German retains
that one English label pending confirmation.

---

## ADR-0008 — Claude Code development system lives at the repository root

**Status:** Accepted · 2026-08-12

`CLAUDE.md`, `.claude/skills/`, `.claude/agents/`, `docs/` and `scripts/hooks/`
sit at the repository root rather than inside `frontend/`, because the system
must govern the backend, database and AI phases too. `.claude/launch.json`
(pre-existing dev-server config) is preserved untouched.

`docs/PROJECT_STATE.md` is the concise status snapshot. Agents and skills are
kept at the repository root so they cover frontend, backend, data and AI work.
Working code remains authoritative when guidance drifts.

---

## ADR-0007 — Product name in code and docs is "Cybrain QS"

**Status:** Accepted · 2026-08-12

The design files render the wordmark **Cybrain QS**, and the implemented UI,
`index.html` title and component copy use it. Written instructions have also
referred to the project as "Cyberen QS". Code and documentation use **Cybrain
QS** to match the artwork.

**Open:** if the official product name is "Cyberen QS", this is a rename across
`CLAUDE.md`, `docs/`, `.claude/`, `Wordmark.tsx` and `index.html`.

---

## ADR-0006 — The design PDF is the visual source of truth, measured not estimated

**Status:** Accepted · 2026-08-12

Layout values are extracted from the design files' vector artwork — element
rectangles from drawing operators, colours sampled from rendered pages, text
positions and sizes from font spans — rather than eyeballed. Implemented screens
were then verified in the browser against those coordinates.

**Consequence:** design tokens in `frontend/src/styles/tokens.css` carry literal
values from the source design. Inconsistencies present in the design file are
reproduced as drawn and raised separately, rather than silently "corrected".

---

## ADR-0005 — CSS Modules with a token layer; no CSS framework

**Status:** Accepted · 2026-08-12

Reproducing a fixed design to a few pixels is simpler with scoped, explicit CSS
than with utility classes or a component library that imposes its own scale.
Tokens live in `styles/tokens.css`; component styles are co-located
`*.module.css`.

**Consequence:** no Tailwind, MUI, Chakra or styled-components. Adding one later
requires a new decision superseding this.

---

## ADR-0004 — Mock data is isolated in `frontend/src/data/`

**Status:** Accepted · 2026-08-12

All placeholder content lives in typed modules under `data/`, never inline in
components. Those modules are the seam a real API client replaces in a later
phase, so the swap touches one directory.

**Consequence:** components receive data via props or page-level state. No
component imports mock data directly except through a page or feature module.

---

## ADR-0003 — No fake backend presented as working

**Status:** Accepted · 2026-08-12 · phase-specific wording updated 2026-09-04

Where a real API exists, the frontend uses it. Where an API is still missing,
the project does not build mock HTTP layers, service workers or stubbed clients
that could be mistaken for working backend functionality.

**Consequence:** e.g. "Neue Firma anlegen", "Dokumente anzeigen" and "Search
Similar Content" render and respond to interaction but perform no action. Their
integration points are documented in `backend/README.md`.

---

## ADR-0002 — Two navigation shells selected per route

**Status:** Accepted · 2026-08-12

The design uses a wide labelled sidebar on company screens and a collapsed icon
rail on the SOP wizard. Rather than one shell with a collapse mode, `AppShell`
takes a `navigation` prop and routes choose. The two are visually distinct
enough in the design that a single component would be mostly branches.

**Revisit** when more screens exist and the split may become a genuine
collapse/expand behaviour.

---

## ADR-0001 — Stack: React + Vite + TypeScript / Python + FastAPI / PostgreSQL

**Status:** Accepted · 2026-08-12

- **React + Vite + TypeScript** for the frontend.
- **Python + FastAPI** for the backend, chosen for the document-processing and
  AI ecosystem this product depends on.
- **PostgreSQL** as the single primary datastore, using **JSONB** for
  variable-shape knowledge payloads and **pgvector** for retrieval embeddings —
  avoiding a separate vector database and keeping company isolation enforceable
  in one place.

**Consequence:** no second backend language, no separate vector store, no second
database engine without an ADR superseding this.

---

## ADR-0016 — Layout-aware ingestion with optional Docling and pluggable OCR

**Date:** 2026-09-18
**Status:** Accepted

**Context:** Real pharma/medtech SOPs vary wildly in heading styles, numbering,
tables and scan quality. Hard-wiring a heavy ML OCR stack into the default
runtime (currently Python 3.14, lightweight deps) is inappropriate, but the
pipeline must still normalize formats into one internal structure and refuse
silent CKM extraction on failed parses.

**Decision:**

- All parsers emit `NormalizedDocument` / `NormalizedBlock` before chunking.
- DOCX stays on python-docx with multi-signal heading detection.
- PDF prefers Docling when installed; pypdf remains the default structured
  fallback.
- OCR is a provider interface (`NullOcrProvider` default); production engines
  are registered explicitly. OCR runs only on pages without a reliable text
  layer.
- Extraction QA returns explicit PASS / WARNING / FAILED. FAILED and
  `needs_ocr` do not proceed into chunking/CKM.

**Consequence:** Core ingest works without Docling/OCR wheels. Production
deployments install Docling and/or register an OCR provider. See
`backend/app/processing/README.md`.

---

# Open questions

Not yet decided. Each needs an ADR before its phase begins.

| Topic | Question | Needed by |
| --- | --- | --- |
| Login screen design | Login is wired, but no approved source design exists; approve or replace the current UI | UI review |
| File storage | Database large objects vs object storage | before durable reprocessing |
| Background jobs | Which runner for ingestion and extraction | before production ingestion |
| Chunking | Validate/tune the implemented structure-aware strategy on real client documents | retrieval hardening |
| Embedding model | Production model, dimensions and re-embedding policy | retrieval hardening |
| Local generation models | Model tier per task and prompt/version management | SOP generation |
| Frontend testing | Test runner and depth of coverage | frontend hardening |
