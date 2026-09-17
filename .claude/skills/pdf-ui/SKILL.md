---
name: pdf-ui
description: Reproduce a Cybrain QS screen from its design PDF accurately — extract exact geometry, colours and typography from the PDF vectors rather than eyeballing, then verify the built screen against those numbers in a browser. Use when implementing or correcting any screen that has a design file, when the user says the UI does not match the design, when adding a component that must match drawn artwork, or when a new design PDF arrives.
---

# Building UI from the design PDFs

The design PDFs are the visual source of truth (`CLAUDE.md` §2). These are
single-page vector exports at a **1440px-wide canvas**, so exact values can be
read out of them. Do not estimate what you can measure.

## Method

### 1. Render and read the design

Rendering needs `pymupdf` (`python -m pip install pymupdf`). Poppler is *not*
installed, so the Read tool cannot rasterise PDFs directly.

```python
import pymupdf
page = pymupdf.open(PDF_PATH)[0]
page.get_pixmap(dpi=144).save(OUT_PNG)   # full page, to look at
page.get_pixmap(matrix=pymupdf.Matrix(6, 6),
                clip=pymupdf.Rect(x0, y0, x1, y1)).save(CROP_PNG)  # zoom an icon
```

Read the full-page PNG first to understand the screen, then crop-zoom every icon
and control you must draw.

### 2. Extract geometry instead of guessing

- `page.get_drawings()` gives every filled shape with its rect, fill and stroke.
  Filter to simple shapes (≤12 path items) — anything larger is a glyph outline,
  because text in these files is drawn as Type3 vector paths.
- `page.get_text("dict")` gives text spans with bbox and size. **Span colours are
  unreliable** (they report black for outlined glyphs) — sample the rendered
  pixels instead.
- For borders, hairlines and anything with opacity, scan a line of pixels across
  the feature in a high-scale pixmap and take the extreme value. Vector fills
  report the pre-opacity colour and will mislead you.
- To locate controls precisely, project a region onto one axis and find runs of
  non-background pixels. That yields exact button boxes, icon centres and row
  pitches.

Write these as throwaway scripts in the scratchpad directory, not in the repo.

### 3. Build against the numbers

Use the existing tokens in `frontend/src/styles/tokens.css` — they were sampled
from these same PDFs. Add a token rather than hard-coding a new colour.

Reproduce the design's own spacing values even when they look slightly
irregular; these files contain real inconsistencies and the rule is to draw what
is drawn.

### 4. Verify in the browser, numerically

Screenshots on this machine are limited by a 1280px physical screen, so an
emulated 1440px viewport renders too small to judge. Measure instead:

```js
// via the browser javascript tool, with the viewport emulated at 1440
const r = document.querySelector(SEL).getBoundingClientRect();
[Math.round(r.left), Math.round(r.top + scrollY), Math.round(r.width), Math.round(r.height)]
```

Compare each element against its PDF rect and iterate until the deltas are small.
**Target: within ~2px.** Font-metric differences (Inter vs the design's font)
legitimately cost a few px on text-sized elements like badges — that is
acceptable and worth noting, unlike a structural offset.

Also confirm computed colours match the sampled tokens, and that
`document.documentElement.scrollWidth === clientWidth` at 1440 / 1280 / 1024.

## Known characteristics of these design files

- Canvas 1440 wide; page height varies per screen.
- Text is Type3 outlines — text extraction fragments words across spans.
- Two navigation shells: a 241px labelled sidebar, and an 87px icon rail.
- The design contains genuine inconsistencies (differing card paddings, a
  search field drawn with a plus glyph, misaligned checkbox columns). Reproduce
  them, then raise them once — do not silently "fix" them and do not leave them
  unmentioned.

## Do not use this skill for

- UI work with no design file — that is `react-frontend` plus a placeholder.
- Pure logic, state or routing changes that do not alter appearance.
- Backend, database or AI work in any form.
- Redesigning. If the design seems wrong, reproduce and raise it.

## See also

`docs/PROJECT_STATE.md` (is UI work allowed right now), `react-frontend` (how the
component layer is organised), `docs/DECISIONS.md` ADR-0005 and ADR-0006.
