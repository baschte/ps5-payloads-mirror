## Context

`mirror_core.py` currently has three payload-mutating entry points:
`add_payload` (append), `update_one`/`update_all` (re-fetch latest release
for an existing entry, driven by `select_update_asset`'s scoring heuristic),
and `remove_payload` (delete). There is no "edit an existing entry" path.
`select_update_asset` picks an asset by scoring name patterns (`ps5` boost,
`ps4` penalty, `install` penalty, preferred extension) with no persisted
memory of what a human actually chose. `add_payload` has a separate, simpler
fallback (`.elf`/`.bin` first, else first `.zip`) and only prompts the user
(`ZipExtractNeeded` → HTTP 422 → `candidates`) when a ZIP has more than one
`.elf` inside — it never prompts when a release has multiple top-level
assets.

The web UI (`AddMirrorForm.tsx`) already implements the "resubmit with
`extract_file` set" pattern for the ZIP-ambiguity case, which is the UI
building block this design reuses for the generalized candidate list.

## Goals / Non-Goals

**Goals:**
- Let a user edit an existing mirror's `description`, source URL, and
  chosen asset/file after creation.
- Make candidate selection (top-level asset AND nested ZIP member) explicit
  and user-driven whenever there's real ambiguity, for both add and edit.
- Keep unattended updates (scheduler/update-all) deterministic and
  prompt-free by relying on a persisted candidate choice rather than
  re-scoring.

**Non-Goals:**
- No search/filter/sort/pagination in the payload table.
- No bulk multi-select partial updates.
- No update history/log UI.
- No change to the on-disk `payloads.json` schema beyond how existing
  `asset_pattern` / `extract_file` fields are populated and interpreted.
- No change to how `payloads.json`'s top-level `name`/`payloads` wrapper or
  `README.md` generation works.

## Decisions

### 1. `edit_payload` replaces the item in place; identity = array position, not `name`

`edit_payload(name, url=None, description=None, extract_file=None,
asset_selector=None)` looks up the existing item by current `name`, and if
`url` is provided, re-resolves the release/asset exactly like `add_payload`
(domain/owner/repo parsing → latest release → candidate list → download/
extract), then overwrites the item's fields (`name`, `filename`, `url`,
`source`, `source_direct`, `version`, `checksum`, `asset_pattern`,
`extract_file`) at its existing index in the `payloads` list. This means the
repo name (and therefore `name`) is allowed to change as a side effect of
editing the URL — it is not a special "rename" operation, just a full field
overwrite at a fixed position.

**Alternative considered**: treat a repo-changing edit as delete+add. Rejected
because it would reorder the list (append instead of in-place) and because
the caller (frontend) already thinks of it as "editing this row" — in-place
replacement matches that mental model and avoids an extra list-position
diff in the UI.

### 2. Duplicate-source check excludes the item being edited

`add_payload`'s duplicate check (`any(p.get("source") == source_url for p in
payloads)`) is reused, but `edit_payload` filters out the item at the
index being edited before running it. This is a plain index/identity
exclusion, not a name comparison, since `name` may itself be changing.

### 3. No-network-change fast path for metadata-only edits

If `url` is not provided (or resolves to the same `source` as today), the
`description` field is patched in place with no network call. If either
`asset_name` (which top-level asset to track) or `extract_file` (which
member of a ZIP-derived asset) differs from what's currently stored, the
source's latest release is re-fetched and the newly specified candidate is
resolved and re-downloaded/re-extracted — still without touching `source`.
This means an asset switch (e.g. from a top-level `.elf` to a `.zip`'s
nested member, or back) does not require the user to also edit the URL: the
edit UI exposes this via a "Change file…" control that proactively fetches
the current source's candidate list on demand (backed by a new read-only
`list_candidates_for_payload` helper / `GET .../candidates` endpoint),
rather than only reactively after an ambiguous URL edit is rejected with a
422. The raw ZIP is not cached after `_extract_zip_member` runs, so "just
pick a different member" pays a re-download regardless of whether the asset
itself changed — deferred, see Open Questions.

**Invariant: an asset switch must reset `extract_file` unless the newly
chosen asset is also a ZIP.** The rebuilt item produced for the new
candidate is merged onto the existing record with `dict.update`, which only
overwrites keys present in the rebuilt dict — it does not delete keys absent
from it. A first implementation missed this: switching a mirror from a
ZIP-derived asset back to a plain `.elf`/`.bin` asset left the old
`extract_file` value stale in the stored record, even though it no longer
applied to anything. The fix explicitly pops `extract_file` from the
in-progress record before merging in the rebuilt fields, so a non-ZIP
target asset always ends up with no `extract_file`, and a ZIP target asset
gets exactly the freshly resolved member name.

### 4. Unified candidate list: `list_candidates(release) -> list[Candidate]`

A new helper builds one flat list per release:
- One entry per top-level asset that is a plausible payload
  (`.elf`/`.bin`/`.zip`, same extension gate `add_payload` uses today).
- For every asset that is a `.zip`, additionally probe its contents (must
  download it to list members — same cost `_extract_zip_member` already
  pays) and append one entry per `.elf`/`.bin` member found inside, tagged
  with which parent asset it came from.

Each `Candidate` carries enough to persist a selection later: `asset_name`
(top-level asset filename — becomes/backs `asset_pattern`) and optionally
`member_name` (becomes `extract_file`, only set for ZIP-nested picks).

`add_payload` and `edit_payload` both call this helper. If
`len(candidates) == 1`, it is auto-selected (today's fast path — most
releases have exactly one `.elf`/`.bin` asset and no ZIP). If more than one
candidate exists and the caller didn't pass an explicit selector, both raise
the existing `ZipExtractNeeded`-style exception (renamed/generalized to
carry the full flattened list, not just ZIP member names) → HTTP 422 with
`candidates` → frontend shows the (now generalized) candidate picker.

**Alternative considered**: keep the two mechanisms separate (asset-level
choice vs. ZIP-member choice as two sequential prompts). Rejected — two
back-to-back "pick one" dialogs for what the proposal frames as one problem
("which file, exactly") is worse UX than one flattened list, and the
frontend's existing dropdown pattern already generalizes to a longer list
with no extra complexity.

### 5. `select_update_asset` becomes a strict stored-candidate filter

Automatic/unattended paths (`update_one`, `update_all`, scheduler) stop
scoring. Instead, given an item's stored `asset_pattern` (top-level asset
identity) and `extract_file` (nested member, if any), the update path:
- Finds the release asset whose name matches the stored `asset_pattern`.
- If found and it's a ZIP with a stored `extract_file`, re-extracts that
  exact member name.
- If not found (renamed/removed asset), raises `MirrorError` — surfaced
  through the existing update-result/toast path unchanged.

**Back-compat for pre-existing entries without a recorded candidate**:
existing `payloads.json` entries were created before this change and may
lack a precise `asset_pattern` (some rely on `select_update_asset`'s old
scoring implicitly). On the first update after this change ships, if an
item has no usable stored candidate, fall back once to the old scoring
heuristic to pick an asset, then **persist that pick** as the item's
`asset_pattern`/`extract_file` so all subsequent updates are deterministic.
This is a one-time, silent migration on first touch — no batch migration
script, no user action required.

**Alternative considered**: require a one-time manual re-pick via the UI for
every existing mirror before automatic updates resume. Rejected as
unnecessary friction — the old heuristic's pick is a reasonable seed, and
recording it going forward achieves the same determinism goal without
forcing action on 12 existing entries that have worked fine so far.

### 6. Error surfacing: no new status field

A stored candidate that disappears from a newer release fails via the
existing `MirrorError` → toast / update-result message. No "needs
attention" flag is added to the data model; the failure is visible exactly
where update failures are visible today.

## Risks / Trade-offs

- **[Risk]** Probing every ZIP asset's contents to build the candidate list
  adds a download for releases that have a ZIP but where the user would have
  been fine with the single top-level `.elf` anyway. → **Mitigation**: only
  probe ZIP contents when the ZIP is itself one of the plausible top-level
  candidates (i.e., skip probing if a non-ZIP `.elf`/`.bin` asset already
  makes the release unambiguous at the top level) — matches today's
  `add_payload` fallback order (elf/bin preferred over zip).
- **[Risk]** In-place field overwrite on a URL-changing edit means a typo'd
  URL edit that resolves to totally unrelated repo silently replaces a
  working mirror's identity. → **Mitigation**: this is the same trust model
  `add_payload` already has (no dry-run/confirmation beyond the existing
  duplicate check); acceptable given this is a single-operator admin UI, not
  multi-tenant.
- **[Risk]** One-time silent re-scoring migration on first post-change update
  could pick a different asset than a human would have, for the ~12
  existing entries with no recorded candidate. → **Mitigation**: this is
  exactly today's existing behavior (same scoring function, same inputs) —
  no regression, just now it gets remembered afterward instead of re-run
  every time.
- **[Trade-off]** No ZIP-content caching across the "change extract_file
  only" edit path means picking a different member inside an unchanged ZIP
  re-downloads the ZIP. Accepted for simplicity; see Open Questions.

## Migration Plan

No data migration step is required before deploy — `payloads.json`'s
existing fields (`asset_pattern`, `extract_file`) are reused as-is, and the
per-item candidate-recording migration described in Decision 5 happens
lazily on each item's first update after deploy. Rollback is a plain
code revert; no schema changes to undo.

## Open Questions

- Should re-picking `extract_file` on an otherwise-unchanged ZIP source
  avoid a full re-download by caching the ZIP temporarily during the edit
  request (single round trip), or is a plain re-download-and-re-extract
  (current proposal) acceptable given ZIPs here are payload-sized (small)?
- Should the candidate list impose a stable sort order (e.g., top-level
  assets first in release-asset order, then ZIP members grouped under their
  parent) so re-showing the picker after a failed selection is visually
  stable? Recommend yes but left to implementation/tasks to pin down exact
  ordering.
