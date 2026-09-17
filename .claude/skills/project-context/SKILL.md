---
name: project-context
description: Orient in the current Cybrain QS repository before doing anything. Loads implementation status, project instructions, architecture and domain vocabulary, then verifies them against code.
---

# Project context

Load this before implementation, planning, review or estimation. It is cheap and
prevents the two expensive mistakes in this project: building the wrong phase,
and using domain terms wrongly.

## Read, in this order

1. **`docs/PROJECT_STATE.md`** — implemented, partial and missing areas.
2. **`CLAUDE.md`** — the constitution. Stable rules across all phases.
3. **`docs/ARCHITECTURE.md`** — only the sections relevant to your task.
4. **`docs/DOMAIN_MODEL.md`** — whenever the task touches domain vocabulary.
5. **`docs/DECISIONS.md`** — before proposing anything structural, to avoid
   re-litigating a settled choice or contradicting one.

Then look at the code you are about to change. Do not skip this: `CLAUDE.md`
describes intent, the code describes reality.

## The scope check

The single most important check:

> Is the requested area implemented, partial or missing in `PROJECT_STATE.md`?

- **Implemented** → inspect and extend the existing path; do not rebuild it.
- **Partial** → identify the real boundary and do only the requested work.
- **Missing** → do not describe it as existing or implement it incidentally.

There is no frontend-only phase gate. Backend, database, document processing,
local inference and retrieval infrastructure exist. Full CKM and SOP workflows
remain incomplete.

## Repository map

```
CLAUDE.md              constitution
docs/                  PROJECT_STATE · ARCHITECTURE · DOMAIN_MODEL · DECISIONS
.claude/skills/        this and the other skills
.claude/agents/        specialist subagents
scripts/hooks/         validation hooks
frontend/              React + Vite + TypeScript app and API clients
backend/               FastAPI, PostgreSQL models/migrations, processing and tests
```

Commands, from the repository root:

```bash
npm --prefix frontend run build    # tsc -b && vite build
npm --prefix frontend run lint     # oxlint
npm --prefix frontend run dev      # :5173
```

## Vocabulary that must not drift

Use `docs/DOMAIN_MODEL.md` terms exactly: **Company / Unternehmen**, **Company
Knowledge Model (CKM)**, **Knowledge Object**, **provenance**, **proposed /
verified**, **Blueprint / Bauplan**, **knowledge tier (Company / Industry /
Global)**, **SOP**, **SOP Version**. The UI runs in English (default) and
German; all strings live in `frontend/src/i18n/`, and the German copy matches
the design files verbatim.

## Do not use this skill for

- Answering a question you can already answer from files open in the
  conversation — just answer.
- Trivial mechanical edits (a typo, a renamed variable).
- As a substitute for reading the actual code being modified.

## Hand off to

- `pdf-ui` and `react-frontend` — building or changing UI.
- `sop-domain` / `ckm-domain` — reasoning about SOP or knowledge semantics.
- `testing-quality` — verifying work before reporting it done.
