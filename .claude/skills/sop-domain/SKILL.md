---
name: sop-domain
description: SOP semantics in Cybrain QS — the six-step creation wizard, Blueprint and knowledge mapping, draft vs approved, versioning, review and approval, and what a regulated SOP must contain. Use when building or reviewing SOP screens, the SOP editor, the creation wizard, SOP search or versioning, and when checking that a flow respects the draft-to-approved gate.
---

# SOP domain

An SOP is a controlled document describing how a regulated process is performed
at a specific company. It is the product's primary deliverable, and in a
regulated setting it is an auditable artefact — that constrains the design more
than a normal document editor would.

## The six-step creation wizard

As drawn in the design files. German labels are the UI copy.

| # | German | English | Purpose | Status |
| --- | --- | --- | --- | --- |
| 01 | Projektinitialisierung | Project initialization | Title, client, why this SOP is needed | **Implemented** |
| 02 | Wissensauswahl | Knowledge selection | Choose which knowledge feeds the SOP | Planned |
| 03 | Bauplan-Editor | Blueprint builder | Define the section structure | Planned |
| 04 | Wissenskartierung | Knowledge mapping | Bind sections to Knowledge Objects | Planned |
| 05 | Entwurfserstellung | Draft generation | Generate the draft | Planned |
| 06 | Überprüfung & Iteration | Review & iteration | Human review and revision | Planned |

The order encodes the product's core belief: **structure and knowledge basis are
decided before prose is generated.** Do not add a "just generate it" shortcut
that skips 03 and 04 — an SOP section with no declared knowledge basis is not
traceable, and traceability is the point.

Step 01 captures: title (with suggestions from the company's existing SOPs), the
client company, SOP context (new process, audit finding, regulatory requirement,
replaces existing, process harmonisation, new customer, other) and optional
free text. Implemented in
`frontend/src/features/sops/ProjectInitializationStep.tsx`; steps 02–06 render a
labelled "no design yet" panel.

## Blueprint / Bauplan

The section outline plus what each section must contain, derived from the
company's document standards, the applicable regulations and any template. The
Blueprint is a first-class object, not a formatting detail — it is where
regulatory required-section rules are satisfied.

## Knowledge mapping

Each Blueprint section is bound to specific Knowledge Objects. Consequences that
must survive implementation:

- Every generated section can name the knowledge it came from.
- Provenance flows from Knowledge Object → section → SOP version.
- A section with no mapped knowledge is visible as such, not quietly filled by
  the model.

## Draft vs approved

```
draft ──▶ in review ──▶ approved ──▶ superseded
```

- A generated draft is **proposed content**. It is never an approved SOP.
- Approval is an explicit human act, recorded with actor and timestamp.
- Approved versions are immutable. Change produces a new version; the previous
  one is superseded, never edited or deleted.
- Never design a flow where generating produces an approved document.

## Versioning

SOPs are versioned, not overwritten. Version history must reconstruct: what the
document said, which knowledge it was based on, who approved it, and when. This
is the audit requirement that makes destructive edits unacceptable.

## Search — two different things

- **SOP search** — find SOP documents by metadata and text.
- **Similar-content search** — retrieve knowledge to support authoring (the
  "Search Similar Content" action in the wizard footer).

Do not implement one and label it the other; they have different scopes,
different results and different UI.

## Reviewing an SOP feature

1. Can a draft reach "approved" without an explicit human approval? → defect.
2. Is every generated section traceable to mapped Knowledge Objects? → if not,
   traceability is broken.
3. Does an edit overwrite an approved version rather than creating a new one? →
   defect.
4. Are the German labels exactly as in the design? → they are regulated-domain
   terms, not free copy.
5. Does the flow let a user mistake AI-generated text for company-verified
   content? → fix the presentation.

## Do not use this skill for

- Knowledge extraction, provenance and tier semantics — that is `ckm-domain`.
- Prompt construction and model choice — that is `llm-generation`.
- Pixel-matching a wizard screen — that is `pdf-ui`.
- Implementing steps 02–06 without a design file or explicit instruction.

## See also

`docs/DOMAIN_MODEL.md` §11–§19, `ckm-domain`, `pdf-ui`,
`frontend/src/constants/wizard.ts`.
