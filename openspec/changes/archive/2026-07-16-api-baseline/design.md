## Context

`server/main.py` is a FastAPI app that has grown organically: mirror CRUD,
a public raw JSON feed, optional Basic Auth, an in-process scheduler
(`server/scheduler.py`), and auto-publish-to-git (`server/auto_publish.py` +
`server/git_ops.py`), all built on top of `mirror_core.py`'s file-backed data
store (`payloads.json` / `hidden_payloads.json`, guarded by `mirror_core.DATA_LOCK`).
None of this is captured as specs today; only four narrow behavioral slices
are (asset candidates, editing, reordering, visibility). This change is
documentation-only: it writes down the requirements the running system
already satisfies, so it becomes the diffable baseline for future changes.

## Goals / Non-Goals

**Goals:**
- Capture the current, shipped behavior of the core management API as
  requirements, split into cohesive capabilities.
- Make each capability's concurrency, security, and error-handling behavior
  explicit enough to test against.
- Give future proposals (e.g. "add pagination", "add API tokens") a baseline
  to diff against instead of starting from the code.

**Non-Goals:**
- No behavior changes, refactors, or new endpoints.
- No spec changes to the four existing capabilities
  (`asset-candidate-selection`, `mirror-editing`, `mirror-reordering`,
  `mirror-visibility`) — they already cover their slices; this change only
  fills the gap around them.
- Not attempting to spec `mirror_core`'s internal resolution/download logic
  in depth (asset scoring, zip extraction) beyond what's needed to state API
  contracts — that belongs to `asset-candidate-selection` and future specs if
  ever revisited.

## Decisions

- **Split into five capabilities, not one monolith.** `mirror-management-api`
  (CRUD + public feed), `collection-title`, `api-authentication`,
  `update-scheduler`, `git-publish`. Each has an independent lifecycle and
  independently-testable requirements, matching how the code is already
  modularized (`git_ops.py`, `scheduler.py`, `auto_publish.py` are separate
  modules). Alternative considered: one `api-baseline` capability covering
  everything — rejected because future deltas (e.g. changing scheduler
  interval limits) would then touch an oversized, unrelated spec file.
- **`api-authentication` is its own capability** rather than folded into
  `mirror-management-api`, because it's cross-cutting middleware that also
  governs access to the scheduler and git-publish endpoints, not just mirror
  CRUD.
- **Document current concurrency guarantees as requirements**, e.g. that
  writes are serialized via `mirror_core.DATA_LOCK` and that a scheduled
  auto-update cannot overlap a manual edit — this is observable, relied-upon
  behavior (comments in `scheduler.py` and `auto_publish.py` call it out
  explicitly), so it belongs in the spec even though it's an implementation
  detail elsewhere.
- **Treat `/payloads.json` and `/api/health` as part of `mirror-management-api`**
  rather than a separate "public feed" capability, since they're just
  unauthenticated views over the same CRUD data with no independent lifecycle.

## Risks / Trade-offs

- [Spec drift risk: writing requirements from current code could accidentally
  encode incidental behavior as a hard requirement] → Mitigation: scenarios
  are scoped to externally-observable API contracts (status codes, auth
  gating, data shape) rather than internal implementation choices; anything
  described as "MUST" is behavior other capabilities or clients already
  depend on.
- [Overlap with existing specs could cause confusing duplication] →
  Mitigation: `mirror-management-api`'s edit/reorder/hide requirements are
  kept to base CRUD only; detailed edit/reorder/visibility semantics stay
  solely in their existing dedicated specs, referenced rather than repeated.

## Migration Plan

Documentation-only; no deployment or rollback needed. Once archived, the five
new spec files land under `openspec/specs/` alongside the existing four.

## Open Questions

None — behavior is fully determined by the existing, shipped code.
