## 1. Candidate resolution core (`mirror_core.py`)

- [x] 1.1 Add a `Candidate` representation (asset name, optional ZIP member
      name) and a `list_candidates(assets, ...)` helper that, given a
      release's assets, returns the flattened list: one entry per plausible
      top-level asset, plus one entry per plausible `.elf`/`.bin` member for
      any top-level asset that is a `.zip` (only probing ZIP contents when
      the ZIP itself is a plausible top-level candidate, per design Risk
      mitigation).
- [x] 1.2 Generalize `ZipExtractNeeded` (or add a new exception) to carry the
      full flattened candidate list, not just in-ZIP `.elf` names.
- [x] 1.3 Add selection logic: if `list_candidates` returns exactly one
      candidate, auto-select it; if more than one and no explicit selector
      was passed in, raise the ambiguity exception with the full list.

## 2. `add_payload` integration

- [x] 2.1 Replace `add_payload`'s current fallback-order asset pick
      (elf/bin-first, else first zip) with a call into the new
      `list_candidates`/selection logic from Task 1.
- [x] 2.2 Accept an explicit candidate selector (top-level asset name, plus
      optional ZIP member) as an add-payload parameter, used when the
      caller is resubmitting after resolving an ambiguity.
- [x] 2.3 Persist the resolved candidate identity into the new item's
      `asset_pattern` (top-level asset) and `extract_file` (ZIP member, if
      applicable) fields.

## 3. `edit_payload` (new)

- [x] 3.1 Implement `edit_payload(name, url=None, description=None,
      extract_file=None, asset_selector=None)` in `mirror_core.py`.
- [x] 3.2 Metadata-only path: when `url` is omitted/unchanged, patch
      `description` (and `extract_file` if changed on an unchanged ZIP
      source, re-downloading/re-extracting only in that case) directly on
      the existing item, no network calls otherwise.
- [x] 3.3 URL-change path: re-resolve via the same repo/release/candidate
      logic `add_payload` uses (reuse Task 1/2 code paths), then overwrite
      the existing item's fields in place at its current list index
      (name, filename, url, source, source_direct, version, checksum,
      asset_pattern, extract_file) instead of appending.
- [x] 3.4 Duplicate-source check: exclude the item being edited (by index,
      not by name) before comparing against other items' `source`.
- [x] 3.5 On any failure (unresolvable URL, no suitable asset, duplicate
      source, ambiguous candidates needing a follow-up choice), raise the
      existing `MirrorError`/`DuplicateError`/ambiguity-exception types
      unchanged, leaving the existing record untouched.

## 4. Automatic update path (`select_update_asset` replacement)

- [x] 4.1 Replace `select_update_asset`'s scoring body with a strict filter:
      find the release asset matching the item's stored `asset_pattern`;
      if it's a ZIP and the item has a stored `extract_file`, use that exact
      member.
- [x] 4.2 If no asset matches the stored `asset_pattern` (or, for a ZIP, no
      member matches the stored `extract_file`), raise `MirrorError` so it
      surfaces through the existing update-result/toast path — no fallback
      guess.
- [x] 4.3 One-time migration-on-touch: if an item has no usable stored
      `asset_pattern`, run the prior scoring heuristic once to pick an
      asset, then persist the result into the item's `asset_pattern`/
      `extract_file` before returning, so later updates skip scoring.
- [x] 4.4 Verify `update_one`/`update_all`/scheduler call sites are
      unaffected beyond consuming the new deterministic result (no prompt
      surfaces from these paths).

## 5. Backend API (`server/main.py`)

- [x] 5.1 Add `PUT /api/payloads/{name}` endpoint accepting
      `{url?, description?, extract_file?, asset_selector?}`, calling
      `mirror_core.edit_payload` under `DATA_LOCK` like the other mutating
      endpoints.
- [x] 5.2 Map the generalized ambiguity exception to an HTTP 422 response
      carrying the flattened candidate list (mirroring today's
      `ZipExtractNeeded` → 422 mapping for `add_payload`).
- [x] 5.3 Ensure `add_payload`'s existing endpoint also surfaces the
      generalized (now possibly-longer) candidate list under the same 422
      contract shape, so the frontend doesn't need two different response
      shapes for add vs. edit.

## 6. Frontend types & API client

- [x] 6.1 Add a `Candidate` type (`web/src/types.ts`) mirroring the backend
      shape (asset name, optional member name, display label).
- [x] 6.2 Update `ApiError`/`toApiError` handling if the 422 candidate shape
      changes (e.g. from `string[]` to structured candidates) — check
      `web/src/api.ts` and `AddMirrorForm.tsx`'s current `candidates: string[]`
      usage.
- [x] 6.3 Add `editPayload()` to `web/src/api.ts` calling the new
      `PUT /api/payloads/{name}`.

## 7. Frontend UI

- [x] 7.1 Generalize `AddMirrorForm.tsx`'s candidate picker (currently a
      `<select>` of ZIP-internal `.elf` names) to render the flattened
      candidate list (top-level assets and nested ZIP members) with clear
      labels distinguishing them.
- [x] 7.2 Add an edit entry point on each row (`PayloadRow.tsx`) — e.g. an
      edit icon/button opening a form pre-filled with the mirror's current
      `source`, `description`, and current candidate selection.
- [x] 7.3 Reuse the generalized candidate-picker UI from 7.1 inside the edit
      form for the case where changing the URL yields ambiguous candidates.
- [x] 7.4 Wire the edit form to `editPayload()`, updating local state
      (`App.tsx`'s `payloads`) in place on success, matching the existing
      `handleUpdated`/`handleRemoved` patterns.
- [x] 7.5 Handle the edit-specific 422 duplicate-source and ambiguity errors
      with appropriate inline messaging (reuse existing toast/error patterns
      from `AddMirrorForm.tsx`).

## 8. Verification

- [x] 8.1 Manually verify: editing only a description patches in place with
      no network calls (check server logs / no asset re-download).
- [x] 8.2 Manually verify: editing a mirror's URL to a different repo
      replaces the item in place (same list position) with the new name.
- [x] 8.3 Manually verify: editing a mirror back to its own current source
      does not trigger a duplicate-source error; editing to another
      mirror's source does.
- [x] 8.4 Manually verify: adding/editing against a release with multiple
      top-level assets prompts with the full candidate list; a release with
      exactly one plausible asset does not prompt.
- [x] 8.5 Manually verify: "Update all" / scheduled run against mirrors with
      a stored candidate does not prompt and picks the same asset as before;
      an existing mirror with no stored candidate gets one recorded on its
      first post-deploy update.
- [x] 8.6 Manually verify: an update whose stored candidate has disappeared
      from the latest release fails visibly (toast/update message) rather
      than silently picking a different asset.

## 9. Asset switch without a source URL change (follow-up)

- [x] 9.1 Add `list_candidates_for_payload(name)` to `mirror_core.py`:
      read-only, re-fetches an existing mirror's current source's latest
      release and returns its flattened candidate list without persisting
      anything.
- [x] 9.2 Add `GET /api/payloads/{name}/candidates` in `server/main.py`
      backed by `list_candidates_for_payload`.
- [x] 9.3 Extend `edit_payload`'s metadata-only path (source URL unchanged)
      to accept `asset_name`, not just `extract_file`, re-fetching the
      release and re-resolving/re-downloading the newly chosen candidate.
- [x] 9.4 Fix: explicitly clear `extract_file` when the metadata-only path's
      merge (`dict.update`) would otherwise leave a stale value after
      switching away from a ZIP-derived asset to a non-ZIP asset.
- [x] 9.5 Add `getPayloadCandidates()` to `web/src/api.ts`.
- [x] 9.6 Add a "Change file…" control to `EditMirrorDialog.tsx` that calls
      the new endpoint, populates the shared `CandidatePicker` proactively,
      and pre-selects the mirror's current asset/member if still present.
- [x] 9.7 Manually verify end-to-end in the browser: switch an existing
      mirror (CheatRunner) from its top-level `.elf` asset to its `.zip`'s
      nested member and back, with the source URL left unchanged, and
      confirm `extract_file` is cleared correctly on the switch back.
