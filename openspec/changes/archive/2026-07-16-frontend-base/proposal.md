## Why

The `web/` frontend (React + Vite + Tailwind) has grown organically alongside the backend API and currently has no corresponding OpenSpec capability — every existing spec in `openspec/specs/` documents backend/API behavior only. Future frontend changes (new features, refactors, redesigns) have nothing to diff against, so there's no shared source of truth for what the UI currently does. This change captures the current frontend as a baseline spec, with no code changes, so subsequent frontend work can proceed spec-first.

## What Changes

- Document the existing frontend as a new `frontend-base` capability spec: app shell/layout, theming, data flow against the backend API, and the behavior of every component (mirror table, add/edit forms, candidate picker, scheduler panel, toasts, drag-and-drop reordering, hide/show, git publish indicators).
- No source code in `web/` is modified by this change — it is a documentation-only baseline.

## Capabilities

### New Capabilities
- `frontend-base`: The web UI's app shell, theming, data-fetching layer, and full set of mirror-management/scheduler/git-publish interactions as currently implemented in `web/src`.

### Modified Capabilities
(none — this change only adds a spec for previously undocumented frontend behavior; it does not alter any existing backend capability's requirements)

## Impact

- Affected artifacts: `openspec/specs/frontend-base/spec.md` (new). No changes to `web/` source, `server/`, or any existing spec.
- Establishes a baseline that future frontend proposals (e.g., refactors, new features, redesigns) can extend via delta specs against `frontend-base`.
