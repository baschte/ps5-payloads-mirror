## Why

The web UI can add and delete mirrors but not edit them — fixing a typo in a
description, correcting a source URL, or switching which release asset is
tracked all require deleting and re-adding. Separately, when a release has
more than one plausible file (multiple top-level assets, or multiple `.elf`
files inside a ZIP), the system sometimes silently guesses via a scoring
heuristic instead of asking, which has picked the wrong asset before.

## What Changes

- Add an edit capability for existing mirrors: source URL, description, and
  asset/file selection can all be changed after creation, not just at
  add-time.
- Edits that only touch `description` patch the stored record in place — no
  network call. Edits that only touch the chosen asset/file (`asset_name`
  and/or `extract_file`) while the source URL stays unchanged re-fetch that
  same source's latest release and re-resolve/re-download the newly chosen
  candidate, without altering `source` itself — so switching which
  top-level asset or ZIP member is tracked no longer requires touching the
  URL.
- A new read-only endpoint (`GET /api/payloads/{name}/candidates`) lets the
  edit UI fetch the full flattened candidate list for a mirror's *current,
  unchanged* source on demand, so the user can see and pick from all
  available assets/files before committing to a change — not only
  reactively, after an ambiguous URL edit is rejected with a 422.
- Edits that change the source URL re-resolve the release exactly like
  add does, then replace the existing record in place (same position),
  instead of appending a new one. The duplicate-source check excludes the
  item being edited.
- Unify asset/file candidate resolution for **both** add and edit into a
  single flattened list: every top-level release asset, plus (for any asset
  that is a ZIP) its `.elf`/`.bin` members flattened into the same list.
  - Exactly one plausible candidate → auto-selected silently (today's fast
    path is preserved).
  - More than one plausible candidate → the user must always choose from the
    full list. This replaces `add_payload`'s current silent fallback-order
    pick for multi-asset releases, and generalizes the existing
    ZIP-ambiguity flow (`ZipExtractNeeded` → HTTP 422 → candidate dropdown)
    to also cover top-level multi-asset ambiguity.
- Automatic/unattended updates (scheduler, "update all", single update
  without a UI) do not prompt. They deterministically resolve to the
  candidate previously chosen at add/edit time (stored as `asset_pattern` /
  `extract_file`) instead of re-scoring assets from scratch. If that stored
  candidate can no longer be found in a newer release, the update fails with
  the existing `MirrorError` path (surfaced via toast / update message) —
  no new status field is introduced.
- **BREAKING (internal only)**: `select_update_asset`'s scoring heuristic is
  replaced by a strict filter against the stored candidate. This only
  affects automatic re-resolution behavior for existing mirrors that have
  never had an explicit candidate recorded (pre-existing entries); see
  design.md for the migration/back-compat handling of those.

## Capabilities

### New Capabilities

- `mirror-editing`: Editing an existing mirror's source URL, description, and
  selected asset/file, including in-place replacement and duplicate-source
  exclusion for the item being edited.
- `asset-candidate-selection`: Unified resolution of plausible release
  candidates (top-level assets and nested ZIP members) shared by add and
  edit, with mandatory user choice when more than one candidate exists and
  silent auto-selection when exactly one exists.

### Modified Capabilities

None — this project has no existing `openspec/specs/` capabilities yet
(add/remove mirror behavior has not previously been captured as a spec), so
add/delete mirror behavior is out of scope for this change and is not being
restated as a modified capability.

## Impact

- **Backend (`mirror_core.py`)**: new `edit_payload` function reusing
  `add_payload`'s repo/release/asset resolution, with its metadata-only path
  accepting an `asset_name` switch (not just `extract_file`) so the tracked
  asset can change without a source URL change; new shared candidate-listing
  helper used by `add_payload` and `edit_payload`; a new
  `list_candidates_for_payload` helper backing the read-only candidates
  endpoint; `select_update_asset` reworked to filter by stored candidate
  instead of scoring.
- **Backend (`server/main.py`)**: new `PUT /api/payloads/{name}` endpoint;
  new `GET /api/payloads/{name}/candidates` read-only endpoint.
- **Frontend (`web/src/api.ts`)**: new `editPayload()` and
  `getPayloadCandidates()` calls.
- **Frontend (`web/src/components/`)**: `AddMirrorForm.tsx`'s candidate-choice
  UI extracted into a shared `CandidatePicker`; new `EditMirrorDialog` with an
  edit entry point on `PayloadRow.tsx`, including a "Change file…" control
  that proactively fetches and shows the current source's candidate list
  (pre-selecting the mirror's current asset/member) independent of whether
  the URL field was touched.
- **Frontend (`web/src/types.ts`)**: types for the flattened candidate list
  and edit request/response shapes.
- No changes to `payloads.json` on-disk schema — reuses existing
  `asset_pattern` and `extract_file` fields.
