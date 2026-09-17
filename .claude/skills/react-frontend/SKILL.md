---
name: react-frontend
description: Write React + Vite + TypeScript code the Cybrain QS way — where components, features, pages, types, constants and mock data belong, how CSS Modules and design tokens are used, and how to keep future backend integration points clean. Use for any change under frontend/, when adding a component, page, route, form control or mock data module, or when deciding whether something is reusable enough for components/common.
---

# Frontend implementation

Stack as built: React 19, Vite 8, TypeScript 6, `react-router-dom` 7, CSS
Modules, oxlint. No CSS framework, no state library, no data-fetching library
(ADR-0005).

## Where code goes

```
frontend/src/
├── components/
│   ├── common/      domain-agnostic and reusable
│   ├── layout/      AppShell, Sidebar, IconRail, Wordmark
│   ├── navigation/  WizardStepper
│   ├── forms/       FieldCard, TextField, TextArea, Checkbox, RadioOption, OptionCard
│   └── sop/         SOP-aware presentational pieces
├── features/        domain-shaped UI: companies/, sops/
├── pages/           route entry points — compose, hold page state, little else
├── routes/          AppRoutes
├── constants/       navigation.ts (ROUTES), wizard.ts, onboarding.ts
├── data/            ALL mock data
├── i18n/            ALL UI strings — en.json, de.json, index.ts
├── types/           shared interfaces
├── utils/           formatDate.ts
└── styles/          tokens.css, global.css
```

The placement test: **does this component know what a SOP or a Company is?**

- No → `components/common/`
- Yes, and it is presentational → `components/sop/`
- Yes, and it owns domain behaviour → `features/<area>/`

Do not put a domain-aware component in `common/`. Do not create a `common/`
component with only one call site "for later".

## Rules that matter here

- **Reuse before duplicating.** Search `components/` and `features/` first. The
  existing `Button`, `Icon`, `StatusBadge`, `SearchInput`, `ProgressBar`,
  `LanguageSwitcher`, `FieldCard`, `Checkbox`, `RadioOption`, `OptionCard`,
  `PageHeader`, `InfoPanel` and `WizardStepper` cover most needs; extend one
  rather than writing a near-copy. `WizardStepper` already serves both wizards
  via its `connected` prop — do not add a second stepper.
- **Icons live in `components/common/Icon.tsx`** as a `IconName` union with
  inline SVG. Add a case there; never inline an SVG in a feature component and
  never add an icon dependency.
- **Mock data only in `frontend/src/data/`**, typed against `src/types/`. No
  inline arrays of fake companies or SOPs inside components. This directory is
  the seam a real API replaces (ADR-0004).
- **No fake backend.** A control that will need a server gets its frontend state
  and interaction only, and stays inert — no stub fetch, no mock service worker,
  no pretend persistence (ADR-0003). Note the integration point instead.
- **Routes come from `constants/navigation.ts`.** Never hard-code a path string
  in a component. Paths are English in every language — they are identifiers,
  not copy, and do not change when the language switches.
- **No user-facing string literals in components.** The UI is English (default)
  and German, switched at runtime. Every visible string — including
  placeholders, `aria-label`s and `title`s — is a key resolved through
  `useTranslation()`, and must be added to **both** `i18n/en.json` and
  `de.json`. German copy matches the design files verbatim. Language-dependent
  mock data is stored as keys, and dates as ISO strings formatted by
  `utils/formatDate`. See ADR-0009.

## Styling

- Design tokens in `styles/tokens.css`; component styles in co-located
  `*.module.css`. Add a token rather than a new literal colour.
- `box-sizing: border-box` is global — width/height values are outer sizes.
- Reset any UA defaults you rely on in `styles/global.css`. `ul`, `ol`, `dl`,
  `dd` are already reset there; a forgotten `ol` margin/padding once cost 16px
  of vertical drift and 40px of horizontal.
- Keep desktop as the reference. Ensure no page-level horizontal overflow at
  1440 / 1280 / 1024, and let wide rows (a stepper, a table) scroll inside their
  own `overflow-x: auto` container rather than pushing the page.

## TypeScript

- `noUnusedLocals`, `noUnusedParameters`, `erasableSyntaxOnly` and
  `verbatimModuleSyntax` are on. Use `import type { … }` for type-only imports.
- Props get a named `interface` above the component.
- Shared shapes go in `src/types/`; do not redeclare a `Company` locally.
- No `any`. No non-null assertions except the single documented `getElementById`
  in `main.tsx`.

## Before reporting a change done

```bash
npm --prefix frontend run build    # tsc -b && vite build
npm --prefix frontend run lint
```

Both must pass, and the browser console must be clean. If the change is visual,
verify it — see `pdf-ui`.

## Do not use this skill for

- Pixel-matching a design PDF — start with `pdf-ui`, come back here for structure.
- Backend, FastAPI, database, AI or RAG work.
- Adding dependencies without a reason recorded in `docs/DECISIONS.md`.
- Building screens that have no design and no placeholder instruction.

## See also

`docs/ARCHITECTURE.md` (frontend layering), `frontend/README.md` (structure and
the two reproduced-as-drawn design quirks), `testing-quality`.
