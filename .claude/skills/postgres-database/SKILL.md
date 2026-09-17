---
name: postgres-database
description: PostgreSQL implementation and schema design for Cybrain QS — SQLAlchemy/Alembic, relational vs JSONB payloads, pgvector, company isolation, provenance and versioning.
---

# PostgreSQL

> **Current state.** PostgreSQL, SQLAlchemy models, Alembic migrations and
> pgvector-oriented chunks exist. Inspect them before schema work; the
> KnowledgeObject model is not a complete CKM workflow.

PostgreSQL is the single primary datastore: relational core, JSONB for
variable-shape knowledge, pgvector for embeddings. No second engine, no separate
vector database (ADR-0001).

## Relational vs JSONB

| Use a column | Use JSONB |
| --- | --- |
| Anything you filter, join or sort on | Type-specific Knowledge Object bodies |
| Identity, ownership, timestamps | Raw extraction output |
| Status, tier, version, type | Structured document analysis |
| Foreign keys | Payloads whose shape varies per `type` |

Never put `company_id`, `status`, `tier`, `type`, `version` or provenance
identity inside JSONB — those are queried on every request and must be indexed
columns. JSONB holds the body, not the metadata.

Index JSONB with GIN only where a real access pattern needs it.

## Company isolation

Every tenant-owned table carries a non-null `company_id` foreign key. This is
the hard boundary from `CLAUDE.md` §4 and it is enforced here, not in the UI.

- `company_id` participates in the primary key or a unique constraint wherever
  natural, and leads composite indexes on hot query paths.
- Cross-company joins must be impossible by construction. Any query without a
  `company_id` predicate on a tenant table is a bug.
- Application-level scoping vs PostgreSQL row-level security is an open question
  in `docs/DECISIONS.md` — resolve it with an ADR before the schema lands.

Industry and Global knowledge live in tables that are explicitly *not*
company-scoped, and are never unioned into a company query without carrying the
`tier` through.

## Provenance and verification

Provenance is columns, not an afterthought stuffed in JSONB. At minimum, on
every Knowledge Object:

`source_document_id`, `source_location`, `extraction_method`, `model_name`,
`model_version`, `extracted_at`, `verified_by`, `verified_at`.

Enforce the invariant in the schema, not only in code: a row with
`status = 'verified'` must have `verified_by` and `verified_at` set — a CHECK
constraint is the right tool.

## Versioning

SOPs and Knowledge Objects are versioned, never destructively updated. Prefer an
append-only version table with a pointer to the current version over an
`UPDATE` that discards history. Superseding sets a status; it does not delete.

Approvals, verifications and status transitions are recorded with actor and
timestamp — a regulated customer must be able to reconstruct who accepted what,
and when.

## pgvector

- Embeddings live beside the chunk they describe, with `company_id` and `tier`
  as filterable columns.
- Fix the embedding dimensionality per column and record the model in
  `docs/DECISIONS.md`; changing model means a migration and a re-embed, not a
  silent mixed index.
- Filter by company and tier **before** vector search, not after.

## Conventions

- `snake_case` tables and columns; plural table names.
- `timestamptz`, always UTC. `uuid` primary keys.
- Enum-like values as PostgreSQL enums or CHECK-constrained text — matched to
  `docs/DOMAIN_MODEL.md` (`proposed` / `verified` / `rejected` / `superseded`;
  `company` / `industry` / `global`).
- Every schema change is a migration. No hand-edited databases.

## Do not use this skill for

- Frontend or API code.
- Retrieval ranking or chunking strategy — that is `rag-retrieval`.

## See also

`docs/DOMAIN_MODEL.md` (entities and lifecycle), `docs/ARCHITECTURE.md`,
`docs/DECISIONS.md` (ADR-0001 and the open questions table), `ckm-domain`.
