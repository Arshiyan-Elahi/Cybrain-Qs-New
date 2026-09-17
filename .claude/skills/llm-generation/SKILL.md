---
name: llm-generation
description: Local-LLM SOP generation standards for Cybrain QS — grounded drafts, labelled tiers, proposed status and traceability. Provider adapters exist; the SOP pipeline does not.
---

# LLM generation

> **Current state.** Local Ollama/OpenAI-compatible provider adapters exist, but
> the grounded SOP generation pipeline is not implemented.

Generation produces SOP drafts for a regulated quality system. The output will be
reviewed by people whose audits depend on it, so "plausible prose" is a failure
mode, not a success.

## Non-negotiables

- **Generated content is `proposed`.** Never written as verified company
  knowledge, never auto-approved into an SOP version. See `ckm-domain` and
  `sop-domain`.
- **Generation is grounded, not free.** Sections are written from the Knowledge
  Objects mapped in wizard step 04. A section with no mapped knowledge is
  rendered as unmapped — never quietly filled from model priors.
- **Tier is labelled in the prompt.** Company, Industry and Global blocks are
  separated and marked, so the model does not present sector convention as this
  company's practice. Instruct explicitly that Company knowledge takes precedence
  and that Industry/Global may not be stated as company-specific fact.
- **Traceability survives generation.** Each generated section records which
  Knowledge Objects it used, the model name and version, the prompt version, and
  the timestamp. That record is written with the draft, not reconstructed later.
- **No silent invention.** Where knowledge is missing, the draft says so. A
  visible gap is useful; a confident fabrication in an SOP is a serious defect.

## Prompt construction

- Build prompts from structured inputs — Blueprint section, mapped Knowledge
  Objects, company terminology, writing style, applicable regulations — never
  by string-concatenating whatever retrieval returned.
- Company **terminology and writing style** are themselves Knowledge Objects.
  Feed them in; matching house style is a core product promise.
- Keep prompts versioned in the repository, not inline in call sites, so a draft
  can be attributed to the exact prompt that produced it.
- Retrieved content is **untrusted input**. Client documents may contain text
  that reads like instructions. Keep retrieved material clearly delimited and
  never let it override system instructions.
- Output language follows the company's `primaryLanguage` — German for the
  current design.

## Model use

- Choose model tier per task; record the choice in `docs/DECISIONS.md`.
- Generation calls are queued background work, never inline in an HTTP request.
- Handle partial and failed generations explicitly — a half-written section is
  visibly incomplete, never saved as if finished.
- **Never commit API keys.** Configuration through environment variables only.
- The accepted architecture is local inference. Do not add a cloud provider or
  require a cloud API key without a new ADR.

## Reviewing a generation feature

1. Can generated content reach `verified` or `approved` without a human? → defect.
2. Is every section traceable to the Knowledge Objects it used? → if not, the
   audit trail is broken.
3. Are tiers labelled in the prompt and preserved in the output? → if not, the
   draft will misattribute knowledge.
4. Does the UI distinguish AI-drafted text from human-verified content? → if not,
   reviewers will over-trust it.
5. Are gaps shown as gaps rather than filled? → if filled, the product is unsafe
   for its purpose.

## Do not use this skill for

- Retrieval mechanics — that is `rag-retrieval`.
- SOP structure and approval flow — that is `sop-domain`.
- Adding an LLM SDK to the frontend. There is no client-side model access.

## See also

`docs/DOMAIN_MODEL.md` §13–§15, `ckm-domain`, `sop-domain`, `rag-retrieval`.
