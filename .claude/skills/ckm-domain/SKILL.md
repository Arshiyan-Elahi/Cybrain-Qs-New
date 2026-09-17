---
name: ckm-domain
description: The Company Knowledge Model — Knowledge Objects, the proposed/verified lifecycle, mandatory provenance, company isolation, and the Company/Industry/Global knowledge tiers. Use whenever work touches extracted knowledge, AI suggestions becoming company knowledge, knowledge tiers or provenance, and when reviewing whether a design would let unverified or cross-company content leak into a CKM.
---

# Company Knowledge Model

The CKM is the structured, company-specific knowledge derived from a company's
own documents. It is what makes a generated SOP sound like *that company's* SOP.

This skill exists to protect four invariants. They come from `CLAUDE.md` §4 and
apply in every phase, in every layer — UI, API, database, retrieval, prompts.

---

## Invariant 1 — AI output is a suggestion, never verified knowledge

Everything an extractor or model produces enters as `proposed`.

```
extraction / AI suggestion → proposed ──human verifies──▶ verified
                                 └────human rejects────▶ rejected
verified ──replaced by a newer version──▶ superseded
```

There is no automatic promotion. No confidence threshold, no "high certainty"
bypass, no bulk import that lands in `verified` without a person. If you are
asked to add one, say why it breaks the model and offer a bulk-accept flow that
still records an actor and stays reversible.

## Invariant 2 — Human verification is an explicit, recorded act

A verification records **who**, **when**, and **what changed**. It is an action a
person takes, not a side effect of another operation. UI that promotes knowledge
must make it obvious that the user is accepting AI output as company truth.

## Invariant 3 — Provenance is mandatory and never reconstructed

Every Knowledge Object carries: source document and version, location within it,
extraction method, model name and version, timestamp, and — once verified — the
verifier and verification time.

Provenance is written on the same path that creates the object. If it cannot be
determined, the object is not created. Never backfill provenance with a guess;
an unattributable fact is worse than a missing one in a regulated system.

## Invariant 4 — Company knowledge is private and tiers do not merge

| Tier | Source | Visible to |
| --- | --- | --- |
| **Company** | The company's own documents and confirmations | That company only |
| **Industry** | Sector norms and common practice | Companies in that industry |
| **Global** | Universal QMS / regulatory baseline | All |

- One company's knowledge must never be readable from another company's context.
  Enforced at the data layer, not the UI.
- Tier travels with the fact — through retrieval, into the prompt, into the
  draft, into what the user sees. Industry or Global content is never stored or
  displayed as if the company authored or verified it.
- "Blending" tiers for a better answer is not a shortcut to take quietly. If a
  task needs it, surface the tier per fact.

---

## Knowledge Object shape

`type` · `payload` · `tier` · `status` · `provenance` · `version`

Types: Terminology · Role · Process · Regulation · DocumentStandard ·
WritingStyle · FormOrRecord.

`payload` is type-specific and variable-shaped (JSONB in the current model);
everything else is queryable metadata and belongs in columns — see
`postgres-database`.

## Review questions

Apply these to any design, schema, endpoint or screen touching knowledge:

1. Can anything reach `verified` without a human action? → defect.
2. Is provenance captured at creation, completely? → if not, defect.
3. Could a query return another company's rows if a filter were forgotten? → the
   isolation is in the wrong layer.
4. Is `tier` preserved end to end, or dropped once retrieval returns? → defect.
5. Does the UI make clear which content is AI-proposed vs company-verified, and
   which tier it came from? → if not, users will trust the wrong thing.
6. Does an update overwrite history instead of creating a version? → defect.

## Current status

The KnowledgeObject persistence model exists. Candidate extraction, review,
verification and CKM management workflows do not. UI summaries do not by
themselves constitute a verified CKM.

## Do not use this skill for

- Pure UI layout or styling work with no knowledge semantics.
- SOP authoring structure and wizard flow — that is `sop-domain`.
- Retrieval mechanics — that is `rag-retrieval`.

## See also

`docs/DOMAIN_MODEL.md` §4–§10, `CLAUDE.md` §4, `postgres-database`,
`rag-retrieval`, `llm-generation`.
