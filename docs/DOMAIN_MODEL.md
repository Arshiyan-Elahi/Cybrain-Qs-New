# Domain Model

The vocabulary of Cybrain QS. Use these terms exactly — in code, in UI copy and
in conversation. Each concept is labelled **Implemented**, **Planned** or
**Proposed** according to what exists in the repository today.

The UI supports English (default) and German. Each concept lists the German
label used on screen where one exists.

---

## 1. Company / Unternehmen — *Implemented (UI only)*

A client organisation. The root of everything: every document, Knowledge Object
and SOP belongs to exactly one Company, and never leaks to another.

| Attribute | German label | Notes |
| --- | --- | --- |
| Name | — | e.g. "Pharma GmbH" |
| Industry | Branche | Pharma, Medizintechnik, Biotechnologie, … |
| Location | Standort | |
| Primary language | Hauptsprache | Drives SOP authoring language |
| Regulations | Regulatorische Anforderungen | See §3 |
| SOP count | SOPs | Documents analysed for this CKM |
| Created / updated | Erstellt am / Zuletzt aktualisiert | |

Current frontend shape: `frontend/src/types/index.ts` → `Company`; live data is
loaded through `frontend/src/services/companies.ts`.

## 2. Company Profile / Company Profile Builder — *Partially implemented*

The Company Profile is the starting point for building a CKM. It captures who
the company is, what regulations bind it, its document standards, terminology
and processes.

- **Implemented:** the profile *view* — `/companies` lists companies and shows
  one company's profile.
- **Implemented:** company creation and profile editing against the backend.
- **Partial:** the broader onboarding flow that builds a CKM.

## 3. Regulation / Regulatorische Anforderung — *Implemented (display only)*

A regulatory framework a company must comply with: `EU GMP`, `FDA`, `ICH Q10`,
`ISO 13485`, `MDR`, `Anhang 11`, …

Regulations constrain SOP content and drive which Knowledge Objects and template
sections are required. Today they are display-only badges.

---

## 4. Company Knowledge Model (CKM) — *Planned*

The structured, company-specific knowledge extracted from a company's own
documents. The CKM is what makes generated SOPs sound like *this* company's SOPs.

A CKM aggregates, per company:

- Terminology and preferred wording
- Document structure and formatting standards
- Writing style
- Roles and responsibilities
- Processes
- Regulations in scope
- Forms and records in use

**CKM status** is surfaced in the SOP UI (`CkmStatusPanel`) with local placeholder
values. Separate company document statistics are loaded from the backend. A
complete CKM management view is not implemented.

> **Rule.** A CKM contains only knowledge derived from that company's material or
> explicitly confirmed by that company. Industry and Global knowledge are
> separate tiers (§9) and are never absorbed into a CKM silently.

## 5. Knowledge Object — *Partially implemented*

The atomic unit of the CKM. A single extracted, typed, traceable piece of
knowledge.

Every Knowledge Object carries:

| Field | Purpose |
| --- | --- |
| `type` | Terminology · Role · Process · Regulation · DocumentStandard · WritingStyle · FormOrRecord |
| `payload` | Type-specific body (JSONB in the implemented model) |
| `tier` | Company · Industry · Global (§9) |
| `status` | **proposed** · **verified** · **rejected** · **superseded** |
| `provenance` | §6 — mandatory |
| `version` | Knowledge Objects are versioned, never silently overwritten |

**Lifecycle**

```
extraction / AI suggestion
        │
        ▼
    proposed ──── human rejects ────▶ rejected
        │
   human verifies
        │
        ▼
    verified ──── replaced by newer ────▶ superseded
```

> **Rule.** Nothing enters `verified` without an explicit human action. There is
> no automatic promotion path, no confidence threshold that bypasses a person.

## 6. Provenance — *Partially implemented*

Mandatory on every Knowledge Object and every generated SOP section. The
KnowledgeObject database model currently requires source document, location,
extraction method and extraction time, with optional model identity and verifier
fields. Creation/review APIs and generated-section provenance are not built.

- Source document identity and version
- Location within the source (page, section, offset)
- Extraction method (rule, parser, model name + version)
- Timestamp
- Verifying human and verification timestamp, once verified

Provenance is what makes the system auditable in a regulated setting. It is
never dropped for convenience and never reconstructed after the fact.

## 7. Human Verification — *Planned*

The gate between AI suggestion and company knowledge. A verification action
records who, when, and what was accepted or changed. Bulk-accept flows must
still record a person and remain reversible.

---

## 8. Document — *Implemented foundation*

An uploaded PDF or DOCX belonging to one Company. Upload, extraction,
structure-aware chunking and persistence are implemented. Candidate Knowledge
Object extraction and durable original-file/version storage are not.

**Document processing** covers: ingestion → text and structure extraction →
chunking → analysis → candidate Knowledge Objects (all `proposed`).

## 9. Knowledge tiers — *Partially implemented*

Three distinct layers with different trust levels and different owners:

| Tier | Source | Visibility |
| --- | --- | --- |
| **Company** | The company's own documents and confirmations | That company only — private |
| **Industry** | Sector norms and common practice | Shared across companies in that industry |
| **Global** | Universal QMS/regulatory baseline | Shared across all |

> **Rule.** Tier travels with the fact — through retrieval, through the prompt,
> into the generated draft, and into the UI. Industry or Global content is never
> displayed or stored as if the company had authored or verified it.

## 10. RAG / Retrieval — *Partially implemented*

The chunk model, optional embeddings and company-prefiltered pgvector retrieval
service exist. Results preserve tier and source location. A registered public
retrieval API, hybrid ranking and end-to-end CKM/SOP use are not implemented.

---

## 11. SOP (Standard Operating Procedure) — *Partially implemented*

The primary deliverable. A controlled document describing how a regulated
process is performed at a specific company.

An SOP has: title, owning Company, purpose/context, structure (Blueprint),
content sections, version, and a review/approval state.

- **Implemented:** SOP creation wizard step 01 only.
- **Planned:** steps 02–06, the SOP Editor, the SOP library, search, versioning,
  review and approval.

## 12. SOP creation wizard — *Step 01 implemented*

Six steps, as drawn in the design:

| # | German label | English | Status |
| --- | --- | --- | --- |
| 01 | Projektinitialisierung | Project initialization | **Implemented** |
| 02 | Wissensauswahl | Knowledge selection | Planned |
| 03 | Bauplan-Editor | Blueprint builder | Planned |
| 04 | Wissenskartierung | Knowledge mapping | Planned |
| 05 | Entwurfserstellung | Draft generation | Planned |
| 06 | Überprüfung & Iteration | Review & iteration | Planned |

**Step 01 captures:** SOP title (with suggestions from the company's existing
SOPs), the client company, the SOP context (why this SOP is needed — new
process, audit finding, regulatory requirement, replaces existing, process
harmonisation, new customer, other) and optional free-text context.

## 13. Blueprint / Bauplan — *Planned*

The structural plan for an SOP before any prose is generated: the section
outline and what each section must contain, derived from company document
standards, applicable regulations and templates.

## 14. Knowledge Mapping / Wissenskartierung — *Planned*

Binding Blueprint sections to specific Knowledge Objects, so each generated
section has a declared, traceable knowledge basis rather than free-floating
model output.

## 15. Draft / Entwurf — *Planned*

LLM-generated SOP content. A Draft is **proposed** by definition. It becomes an
approved SOP version only through review and approval (§18).

## 16. Roles and Responsibilities — *Planned*

Company-specific roles (QA Manager, Production Lead, …) and what each is
accountable for. Extracted as Knowledge Objects; used to populate SOP
responsibility sections.

## 17. Workflows, Forms and Records — *Planned*

- **Workflow** — an ordered process the company performs, referenced by SOPs.
- **Form / Record** — a document produced or filled in when executing a
  procedure. SOPs reference the forms they require.

## 18. Versioning, Review and Approval — *Planned*

SOPs and Knowledge Objects are versioned; nothing is destructively overwritten.
An SOP version moves through draft → in review → approved → superseded, with
approvals recorded against a person and a timestamp.

## 19. Search — *Planned*

Two distinct things, not to be conflated:

- **SOP search** — finding SOP documents by metadata and text.
- **Similar-content search** — retrieval over the knowledge base to support
  authoring ("Search Similar Content" in the wizard footer).

---

## Relationships

```
Company (1) ──── (n) Document
   │                    │
   │                    └── (n) Knowledge Object ── (1) Provenance
   │                                  │
   │                                  ├── tier: Company | Industry | Global
   │                                  └── status: proposed → verified
   │
   ├──── (1) Company Knowledge Model ─── aggregates verified Knowledge Objects
   │
   └──── (n) SOP
              └── (n) SOP Version ── Blueprint ── (n) Section
                                                      │
                                     Knowledge Mapping┘  → Knowledge Objects
```

## Terminology discipline

| Use | Not |
| --- | --- |
| Company / Unternehmen | client, tenant, org (in UI copy) |
| Knowledge Object | fact, item, entity |
| proposed / verified | draft-approved, auto-approved |
| Blueprint / Bauplan | outline, template (Template is a separate concept) |
| CKM | knowledge base, memory |
