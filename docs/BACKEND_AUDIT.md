# Backend architecture audit (historical pre-refactor baseline)

This file records the problems found before the current domain-module refactor.
Its old paths are evidence from that baseline, not a description of today's
layout. `PROJECT_STATE.md` and the current code describe remaining debt.

Findings from the pre-refactor codebase, each verified against the source
rather than assumed. Severity is about production risk, not tidiness.

| # | Finding | Evidence | Severity |
| --- | --- | --- | --- |
| 1 | Modules grouped by **technical type**, not domain. Adding a feature touches 5 directories. | `models/ schemas/ services/ repositories/ api/` | High |
| 2 | **No dependency injection.** Services construct their own repositories; routers construct services. Nothing can be substituted in a test. | 19 call sites of `Service(db)` / `Repository(db)` | High |
| 3 | **No transaction boundary.** Services call `db.commit()` themselves, so a multi-step operation can half-commit. | 8 scattered `db.commit()` | High |
| 4 | **No test suite.** "Tests" are scripts requiring a live server and a live database. Cannot run in CI, cannot test a unit. | no `tests/`, 3 ad-hoc scripts | High |
| 5 | **No logging of any kind.** No request ids, no error records, nothing to debug production with. | zero `logging` imports | High |
| 6 | **Login is brute-forceable.** No rate limiting, no lockout. | `api/v1/auth.py` | High |
| 7 | **Authorization is dead code.** `UserCompanyAccess.role` is stored and never read; every member is effectively an owner. | `.role` never referenced | High |
| 8 | Config resolved **at import time**, so settings cannot be overridden per test and the app cannot be constructed twice. | `settings = get_settings()` in 4 modules | Medium |
| 9 | **Schema shape depends on the environment at import.** The pgvector column width is read from config when the model module loads. | `models/document.py:13` | Medium |
| 10 | **Unbounded list responses.** No pagination anywhere. | `GET /companies`, `GET /documents` | Medium |
| 11 | **Blocking work inside the request.** `async def upload_document` performs synchronous parsing and database I/O, stalling the event loop for the duration of a 25 MB parse. | `api/v1/documents.py:18` | Medium |
| 12 | Circular imports worked around with bottom-of-file imports. | `noqa: E402` in two models | Medium |
| 13 | **Uploaded bytes are discarded** after parsing, so a document can never be re-processed or re-embedded from source. | `services/ingestion.py` | Medium |
| 14 | CORS allows all methods and headers **with credentials enabled**. | `main.py` | Medium |
| 15 | `SECRET_KEY` has a working default, so a misconfigured deploy silently runs with a known signing key. | `core/config.py` | Medium |
| 16 | No security headers, no request size limit beyond the upload check. | `main.py` | Low |
| 17 | Tokens cannot be revoked; no refresh token, no `jti`. | `core/security.py` | Low |
| 18 | Response construction duplicated across document endpoints. | `api/v1/documents.py` | Low |

## What this refactor addresses

Findings 1–12, 14, 15 and 18. See `docs/ARCHITECTURE.md` for the resulting
structure and `docs/DECISIONS.md` for the reasoning.

## Deliberately deferred

- **13 (raw file retention)** — needs an object-storage decision first.
- **17 (token revocation)** — needs Redis or a token table; see the
  pre-production checklist in `backend/README.md`.
