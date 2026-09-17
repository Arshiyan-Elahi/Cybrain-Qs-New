---
name: testing-quality
description: Verify Cybrain QS work before calling it done — run the real build and lint, check the browser console and layout, measure UI against the design, and report honestly what passed and what was skipped. Use before reporting any change complete, when reviewing a diff, and when deciding what is worth testing at the current phase.
---

# Verification and quality

The rule underneath all of this: **never report something as working that you
have not run.** If a check was skipped, say so.

## Always run before reporting done

From the repository root:

```bash
npm --prefix frontend run build    # tsc -b && vite build — must exit 0
npm --prefix frontend run lint     # oxlint
```

The build is the type check — `tsc -b` runs first. There is no separate
`typecheck` script.

A `PostToolUse` hook type-checks the frontend after edits and a `Stop` hook runs
the build when frontend sources changed, so failures surface automatically. That
does not remove the obligation to check the result yourself.

## For UI changes, also

1. **Browser console clean** — no errors, no React warnings.
2. **No horizontal overflow** at 1440 / 1280 / 1024:
   `document.documentElement.scrollWidth === document.documentElement.clientWidth`.
   Wide rows must scroll inside their own container, not push the page.
3. **Geometry against the design** — measure element rects and compare to the PDF
   values. See `pdf-ui`. Target ~2px; note font-metric differences separately.
4. **Interactions actually work** — drive them and read the resulting DOM.
   React state updates are asynchronous: `await` a tick after a click before
   asserting, or you will read stale content and wrongly conclude it is broken.

Screenshots are unreliable here — the physical screen is 1280px, so an emulated
1440px viewport renders too small to judge. Prefer measurement over eyeballing,
and say when a visual check was not possible.

## Reviewing a change

- **Scope** — does the diff touch only what the task needed? Unrelated edits are
  a defect regardless of quality.
- **Phase** — does it stay inside what `docs/PROJECT_STATE.md` allows?
- **Reuse** — is this a near-copy of an existing component, type or helper?
- **Placement** — does a domain-aware component sit in `components/common/`?
  Does mock data sit outside `src/data/`? Is a route hard-coded instead of
  coming from `constants/navigation.ts`?
- **Dead code** — unused exports, an abandoned component, a leftover scaffold
  file. Remove it rather than leaving it.
- **Design fidelity** — for visual work, was it measured or guessed?
- **Domain invariants** — for anything touching knowledge or SOPs, apply the
  review questions in `ckm-domain` and `sop-domain`.

## Testing depth by phase

The backend has a pytest suite; run relevant tests for backend changes. The
frontend has no automated test runner, so verification remains build, lint,
console, measured layout and driven interactions. Do not add a frontend test
framework as a side effect of unrelated work.

Business rules, company isolation, provenance completeness and the
proposed→verified gate require automated coverage as those workflows are built.

## Reporting

State what you ran and what it returned. If tests fail, show the output. If you
skipped a check, name it. Do not hedge a verified result and do not present an
unverified one as verified.

## Do not use this skill for

- Adding a test framework or CI without an explicit request.
- Writing product code — this is verification and review only.
- Replacing a real run with an assertion that it "should" pass.

## See also

`CLAUDE.md` §5–§6, `docs/PROJECT_STATE.md`, `pdf-ui`, `react-frontend`,
`scripts/hooks/`.
