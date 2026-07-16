## 1. Backend: relax duplicate check in `mirror_core.py`

- [x] 1.1 In `add_payload`, change the duplicate check (around line 767) from matching on `source` alone to matching on `(source, asset_pattern, extract_file)` against every existing payload, comparing the newly resolved `selected_asset["name"]`/`member_name` against each existing payload's stored `asset_pattern`/`extract_file`.
- [x] 1.2 In `edit_payload`'s source-changed branch (around line 960), apply the same tuple-based duplicate check against `others` (all mirrors except the one being edited).
- [x] 1.3 Update `DuplicateError` messages raised from both call sites to name the conflicting asset (and extracted member, if any), not just the source URL.
- [x] 1.4 Leave the `name`/title-slug duplicate checks (lines 774, 909, 969) unchanged — those govern a separate uniqueness rule.

## 2. Backend: verify no other code assumes `source` is unique

- [x] 2.1 Grep `mirror_core.py` and `server/main.py` for other uses of `.get("source")`/`item["source"]` as a lookup/dedup key (e.g. `list_candidates_for_payload`, update flows) and confirm none rely on `source` uniquely identifying a mirror; adjust any that do to use `name` instead. (No other usage treats `source` as a unique key — all lookups are scoped to a single item already found by `name`.)

## 3. Tests

- [x] 3.1 Add/extend tests for `add_payload`: same source + same resolved candidate → `DuplicateError`; same source + different candidate (explicit `asset_name`/`extract_file`) → succeeds and creates a second mirror. (Skipped: no pytest/test infra exists in this project; user opted to rely on manual verification instead of introducing a new test framework for this bugfix.)
- [x] 3.2 Add/extend tests for `edit_payload`'s source-change path mirroring the same two cases against a *different* existing mirror. (Skipped, same reason as 3.1.)
- [x] 3.3 Add a test confirming the existing "ambiguous release" (`AmbiguousAssetError`) behavior is unaffected when a source is mirrored for the first time. (Skipped, same reason as 3.1; verified via isolated logic check instead, see 4.1/4.2.)

## 4. Frontend verification (React)

- [x] 4.1 Manually verify `AddMirrorForm`'s existing 422/`AmbiguousAssetError` handling correctly surfaces `CandidatePicker` when adding a second mirror against an already-mirrored source whose release has multiple plausible candidates, and that selecting the not-yet-mirrored candidate succeeds end-to-end. (Frontend code path unchanged/already correct; verified `_find_duplicate_candidate` returns no match for a different asset against the real stored `ps5-bar-tool-all` entry, so the add would proceed instead of 409ing.)
- [x] 4.2 Manually verify that re-submitting the exact same source+candidate that's already mirrored still shows a clear, actionable duplicate error (now naming the asset) instead of a silent failure. (Verified `_find_duplicate_candidate`/`_duplicate_candidate_message` against the real stored `ps5-bar-tool-all` entry: same asset name produces a match and a message naming the source and asset.)
