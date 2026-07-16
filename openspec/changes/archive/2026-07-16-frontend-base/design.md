## Context

The `web/` frontend (React 18 + Vite + Tailwind v4, `web/src/App.tsx` and `web/src/components/*`) has been built up over several prior changes without ever being captured as an OpenSpec capability. All existing specs in `openspec/specs/` describe backend/API behavior. This change is documentation-only: it produces `specs/frontend-base/spec.md` by directly reading the current implementation, with no code changes to `web/`.

## Goals / Non-Goals

**Goals:**
- Produce a `frontend-base` spec whose requirements and scenarios are traceable to actual current behavior in `web/src`.
- Give future frontend changes (refactors, new features, redesigns) a baseline to diff against via delta specs.

**Non-Goals:**
- No refactoring, restructuring, or behavior changes to `web/` source.
- No new frontend architecture decisions (routing, state management library, component library) — those are out of scope until a future change proposes them.
- Not an exhaustive UI/UX style guide (colors, spacing, exact copy) — the spec covers functional behavior, not visual design detail.

## Decisions

- **Spec derived directly from source, not from memory or assumptions.** Each requirement in `specs/frontend-base/spec.md` maps to concrete logic in `App.tsx`, `api.ts`, or a specific component file. Alternative considered: write a high-level/aspirational spec — rejected because it would immediately drift from reality and defeat the purpose of a baseline.
- **Single capability (`frontend-base`) rather than one per component.** The frontend today is a single cohesive app shell with tightly coupled state (e.g., `busyName`, `gitEnabled`/`gitPending` derived from mutations), not independent capabilities. Splitting into per-component specs (e.g., `scheduler-panel`, `mirror-table`) would fragment a single interaction model prematurely. Future changes can split it if the frontend grows distinct capability boundaries.
- **No design-only sections for visual styling.** Tailwind theme tokens, fonts, and animation classes are implementation detail, not testable requirements, so they're omitted from the spec itself (they remain visible in `web/src/styles.css` if needed).

## Risks / Trade-offs

- [Spec drifts from code immediately after this change, since no enforcement ties them together] → Mitigation: treat `frontend-base` as the required base for any future frontend proposal, using delta specs (`## MODIFIED Requirements`) so drift is caught at proposal time.
- [Baseline may omit minor edge-case behavior not surfaced during exploration] → Mitigation: this is acceptable for a first baseline; gaps can be added via a small follow-up delta once noticed, rather than blocking this change.

## Migration Plan

Not applicable — no code or runtime changes. Once this change is applied, `frontend-base` becomes a permanent spec under `openspec/specs/`.
