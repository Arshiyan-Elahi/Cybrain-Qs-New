# Cybrain QS — Frontend

React + Vite + TypeScript reproduction of the Cybrain QS design PDFs.
**This phase is frontend only** — no backend, database, API, auth, AI or RAG.
All data comes from local mock modules in `src/data/`.

## Run

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # tsc -b && vite build
```

## Screens

| Route | Screen | Source |
| --- | --- | --- |
| `/companies` | Company Profiles (CKM entry screen) | `Cybrain QS Dashboard Design.pdf` |
| `/companies/new` | Client onboarding — section 0 START | `Cybrain QS Neue Firma anlegen Dashboard Design.pdf` |
| `/sops/new` | Create SOP — step 01 Project initialization | `Cybrain QS Neue SOPs Dashboard Design.pdf` |
| `/sops`, `/workflows`, `/knowledge`, `/assistant`, `/records`, `/alerts` | Placeholders | Icon-rail entries with no design yet |

Route paths are English in both languages — they are stable identifiers, not UI
copy, so they do not change when the language is switched.

Only these three screens are designed in the source PDFs. SOP wizard steps 02–06
and client onboarding sections 02–15 exist in their steppers and are navigable,
but render a "no design yet" panel.

The onboarding screen's "Zusammenfassung der KI-Analyse" figures are **mock AI
output**. When a backend supplies them they must stay marked as proposed and
carry provenance — see `.claude/skills/ckm-domain`.

## Structure

```
src/
├── components/
│   ├── common/      Icon, Button, StatusBadge, SearchInput, InfoPanel, PageHeader
│   ├── layout/      AppShell, Sidebar, IconRail, SidebarFooter, Wordmark
│   ├── navigation/  WizardStepper
│   ├── forms/       FieldCard, TextField, TextArea, Checkbox, RadioOption
│   └── sop/         CkmStatusPanel, SopSuggestionList
├── features/
│   ├── companies/   CompanyListPanel, CompanyListItem, CompanyDetailCard, SopCountCard
│   └── sops/        ProjectInitializationStep
├── pages/           CompaniesPage, CreateSopPage, PlaceholderPage
├── routes/          AppRoutes
├── constants/       navigation.ts, wizard.ts
├── data/            companies.ts, sopProjects.ts   ← all mock data lives here
├── i18n/            en.json, de.json, index.ts     ← all UI strings live here
├── types/           shared TypeScript interfaces
├── utils/           formatDate.ts
└── styles/          tokens.css, global.css
```

## Languages

English (default) and German, switched at runtime from the selector in each
screen's top row. Components render translation keys only — add new copy to
**both** `src/i18n/en.json` and `src/i18n/de.json`. The choice persists in
`localStorage` under `cybrain-qs.language`. See ADR-0009 in `../docs/DECISIONS.md`.

## Design fidelity

Layout values were measured from the PDF vector artwork rather than estimated:
colours were sampled from the rendered pages and element boxes were read from
the drawing operators. Both screens were then verified in the browser at a
1440px viewport — every measured element lands within ~2px of its position in
the design, except badge widths (±7px, a font-metrics difference between Inter
and the font used in the design file).

Design tokens live in `src/styles/tokens.css`. Key values:

| Token | Value | Use |
| --- | --- | --- |
| `--c-brand` | `#5933C3` | Primary purple |
| `--c-page` | `#FBFBFB` | Page background |
| `--c-surface` | `#FDFDFD` | Cards |
| `--c-surface-soft` | `#F9F9FD` | Sidebar, info callout |
| `--c-border` | `#CFCFCF` | Card / input borders |
| `--c-border-strong` | `#8E8E8E` | Section rules in the detail card |
| `--c-brand-badge` | `#F2EFF9` | Regulation badges |
| `--c-brand-soft` | `#EEEBF9` | Active sidebar pill |

### Two things reproduced as-drawn

1. **The company search field uses a plus glyph, not a magnifier.** The design
   file draws a `+` inside "Firma suchen…". Reproduced as drawn — worth
   confirming whether that was intentional.
2. **The selected company row gets extra spacing.** The design puts a rule and
   ~22px of extra space below the highlighted row only. Reproduced, which means
   rows below the selection shift slightly when the selection changes.

Checkbox columns in the SOP context block are inconsistent in the source: row 1
uses three columns at 190 / 386 / 604, rows 2–3 use two columns at 190 / 442.
This is reproduced as drawn via two grids (`contextRowPrimary` /
`contextRowSecondary`) rather than normalised into one aligned grid.

## Backend integration points

Nothing here calls a server. The places a backend will plug in are listed in
`../backend/README.md`.
