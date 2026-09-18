---
name: document-processing
description: PDF/DOCX ingestion for Cybrain QS — implemented extraction and structure-aware chunking, plus future provenance-complete candidate Knowledge Object extraction.
---

# Document processing

> **Current state.** PDF/DOCX extraction, scanned/mixed/digital classification,
> optional Docling PDF path, pluggable OCR provider, structure normalization,
> extraction QA (PASS/WARNING/FAILED), structure-aware chunking and persistence
> are implemented. Candidate Knowledge Object extraction and the
> provenance/verification workflow are not.

Client documents — existing SOPs, templates, policies — are the raw material the
CKM is built from. This pipeline is the origin of provenance, so getting it right
determines whether the whole system is auditable.

## Pipeline

```
upload ──▶ classify ──▶ format extract ──▶ normalize ──▶ extraction QA
                                                          │
                     chunk ◀── (PASS/WARNING only) ◀──────┘
                     (FAILED / needs OCR does not enter CKM)
```

Each stage records what it did. A Knowledge Object emitted at the end must be
traceable back through every stage to a byte range in a specific document
version.

## Rules

- **Documents are immutable once ingested.** Re-uploading the same file produces
  a new document version; it never mutates the existing one. Downstream
  Knowledge Objects keep pointing at the version they came from.
- **Every document belongs to exactly one Company** and is scoped from the moment
  of upload. There is no "unassigned" state.
- **Everything extracted is `proposed`.** The pipeline never writes `verified`.
  See `ckm-domain`.
- **Provenance is captured during extraction, not after.** Source document id and
  version, location within the document, extractor identity and version,
  timestamp. If location cannot be determined, that is a pipeline defect, not an
  acceptable null.
- **Parsing failures are surfaced, not swallowed.** QA status is explicit
  PASS / WARNING / FAILED from observable checks — never invented confidence
  percentages. FAILED extraction must not proceed into CKM extraction.

## Structure matters more than text

SOPs are highly structured — numbered sections, responsibility tables, step
lists, referenced forms, revision history. Extracting a flat text blob throws
away exactly the signal the CKM needs.

Preserve: heading hierarchy and numbering, tables as tables, lists as lists,
headers/footers (they carry document control metadata; mark repeated furniture
non-semantic), approval/signature blocks, revision history and appendices.

Parsers emit a shared `NormalizedDocument` / `NormalizedBlock` schema before
chunking. Fixed SOP section names (PURPOSE/SCOPE/…) are weak hints only.

## Chunking

Chunk on document structure — section and subsection boundaries — not on a fixed
character count that splits mid-table or mid-procedure. Each chunk keeps its
heading path so retrieval knows where it came from. Non-semantic furniture is
excluded from embeddings unless explicitly required.

## Practical notes

- PDF: Docling is preferred when installed; pypdf is the built-in fallback.
- Scanned/mixed pages invoke the pluggable OCR provider only where the text
  layer is unreliable. Default provider records the need without inventing text.
- Recommended production OCR: Docling OCR, Tesseract/ocrmypdf with layout output.
- Long-running work is queued, never done inside an HTTP request.
- Uploaded files are untrusted input: validate type and size, and never execute
  or template anything derived from document content.
- File storage location is an open question in `docs/DECISIONS.md`.

## Do not use this skill for

- Reading the *design* PDFs to build UI — that is `pdf-ui`, a completely
  different activity.
- Retrieval and ranking over chunks — that is `rag-retrieval`.
- Knowledge lifecycle semantics — that is `ckm-domain`.

## See also

`docs/DOMAIN_MODEL.md` §5–§8, `ckm-domain`, `postgres-database`,
`backend/app/processing/README.md`, `docs/DECISIONS.md` open questions.
