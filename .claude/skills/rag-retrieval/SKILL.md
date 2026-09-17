---
name: rag-retrieval
description: Tier-aware pgvector retrieval for Cybrain QS — existing infrastructure, hard company isolation, preserved tiers/source provenance, and future API and ranking work.
---

# Retrieval / RAG

> **Current state.** A company-prefiltered pgvector retrieval service exists,
> but it is not exposed as a complete API and the CKM/SOP workflow is missing.

Retrieval here is not generic RAG. Two constraints make it specific: results
cross a **privacy boundary between companies**, and they cross a **trust
boundary between knowledge tiers**. Both must survive into whatever the user
finally sees.

## Non-negotiables

### Company isolation is a pre-filter, never a post-filter

Filter by `company_id` **before** the vector search, in the query. Never retrieve
broadly and drop foreign rows afterwards — one missed branch leaks another
company's SOP content, which in this domain is a serious breach, not a bug.

There is no "search across all companies" mode. Industry and Global knowledge
live in their own non-company-scoped tables and are queried deliberately.

### Tier travels with every hit

Each result carries its tier — **Company**, **Industry** or **Global**. The tier
must survive: retrieval → ranking → prompt → generated draft → UI.

- Never return an undifferentiated merged list.
- Never let Industry or Global content be presented as the company's own
  verified knowledge.
- When mixing tiers in one prompt, label each block by tier so the model — and
  anything reading the output — can tell them apart.

### Provenance comes back with the content

Every hit returns source document, version, location and the knowledge status
(`proposed` / `verified`). Retrieval that returns bare text makes downstream
traceability impossible to reconstruct.

Decide deliberately whether a given retrieval may return `proposed` knowledge.
For authoring support it may, clearly marked. For anything presented as
established company practice, restrict to `verified`.

## Design notes

- **Chunking** is structure-based, done in `document-processing`. Retrieval
  quality is mostly decided there; do not compensate for bad chunks with clever
  ranking.
- **Embedding model** and dimensionality are fixed per column and recorded in
  `docs/DECISIONS.md`. Changing model means a migration and a full re-embed —
  never a mixed index.
- **Hybrid retrieval** — vector plus lexical — suits this domain, because
  regulatory identifiers (`ICH Q10`, `Anhang 11`, form numbers) are exact strings
  that embeddings handle poorly.
- **Rank with tier awareness.** A verified Company fact should generally outrank
  a semantically closer Global one for company-specific questions. Make that
  policy explicit, not an accident of cosine distance.
- **Return enough context to be useful**: heading path, section number, and the
  neighbouring text a reviewer needs to judge the hit.

## Evaluating retrieval

Before calling retrieval good, check on real client-shaped documents:

1. Does any query ever return another company's content? Must be provably never.
2. Is tier correct on every hit?
3. Do exact regulatory identifiers retrieve reliably?
4. Are chunks whole — no split tables, no half procedures?
5. Is provenance complete enough for a reviewer to find the source passage?

## Do not use this skill for

- Prompt construction and generation — that is `llm-generation`.
- Chunking and parsing — that is `document-processing`.
- Schema and index design — that is `postgres-database`.

## See also

`docs/DOMAIN_MODEL.md` §9–§10, `ckm-domain` (tier and provenance invariants),
`docs/DECISIONS.md` open questions.
