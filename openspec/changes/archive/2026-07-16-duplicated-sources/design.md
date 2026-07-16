## Context

`add_payload` and `edit_payload` in `mirror_core.py` both reject a request whenever the resolved `source` URL (`https://{domain}/{owner}/{repo}/releases`) matches any existing mirror's `source`, regardless of which asset/file was actually selected from that release. A releases page can have multiple plausible assets (or ZIP-extractable members), each meant to become its own mirror, and the current check makes that impossible: the second add for the same repo always 409s before the user even gets a chance to pick a different candidate.

Every stored mirror already records exactly which candidate it mirrors via `asset_pattern` (the top-level asset filename) and, when applicable, `extract_file` (the ZIP member name). These two fields, together with `source`, fully identify what a mirror actually points at.

## Goals / Non-Goals

**Goals:**
- Allow multiple mirrors to share the same `source` when they mirror different assets/files.
- Still prevent a true duplicate: same `source`, same `asset_pattern`, same `extract_file`.
- Keep the ambiguous-release flow (candidate picker) as the mechanism a user goes through to pick which asset, both on first add and on a second add against an already-mirrored source.

**Non-Goals:**
- No change to how candidates are resolved/scored (`resolve_candidate`, `list_candidates`) — this change only touches the duplicate-check predicate.
- No change to `name`/slug uniqueness rules — `name` remains the unique key for a mirror's identity (filename, URL path), untouched by this change.
- No backfill/migration of existing `payloads.json` data.

## Decisions

**Duplicate key becomes `(source, asset_pattern, extract_file)` instead of `source` alone.**
Both `add_payload`'s check (mirror_core.py:767) and `edit_payload`'s two checks (mirror_core.py:892, mirror_core.py:961) compare against this tuple. `extract_file` is `None` for non-ZIP assets, which naturally distinguishes "same top-level asset" mirrors from "different member of the same ZIP" mirrors.

Alternative considered: drop the duplicate check entirely and rely only on `name` slug collisions. Rejected — a user re-submitting the exact same URL with no differing selection (e.g. double-click, or forgetting they already mirrored the exact same asset) should still get a clear, immediate rejection rather than silently creating a second identical mirror under an auto-generated `repo`-based name collision path (which would itself then fail on the `name` check anyway, but with a more confusing error).

**Forcing candidate disambiguation on a repeat add against a known source.**
Today, `_resolve_release_and_asset` auto-selects when exactly one plausible candidate exists — fine for the first mirror of a repo. For a *second* add against the same source, auto-selecting the same single candidate would just reproduce the exact duplicate every time with no path forward. Since `resolve_candidate` already raises `AmbiguousAssetError` whenever more than one plausible candidate exists, and the frontend already handles that by showing `CandidatePicker`, the practical fix is: the duplicate check happens *after* candidate resolution (as it already does), and it only blocks when the resolved candidate truly matches an existing mirror. If a release genuinely has only one plausible asset and that asset is already mirrored, the request still correctly fails as a true duplicate — there is nothing else to mirror. If it has multiple plausible assets, `AmbiguousAssetError` already fires and the picker lets the user choose the other one, which then passes the relaxed duplicate check.

No new backend disambiguation path is needed beyond the existing `AmbiguousAssetError`/candidate-picker flow — the fix is purely narrowing what counts as a duplicate.

**Error message includes the asset/file, not just the source.**
`DuplicateError(f"A payload from {source_url} already exists.")` becomes something like `f"A payload from {source_url} using {asset_pattern}{' ({extract_file})' if extract_file else ''} already exists."` so the rejection is actionable when it does occur.

**Frontend**: `AddMirrorForm` already re-shows `CandidatePicker` on any 422 (`AmbiguousAssetError`). No change is needed there for the multi-candidate case. The only frontend touch is cosmetic: none required functionally, since the backend change alone unblocks the described scenario (release with 2+ assets, one already mirrored — picking the other now succeeds). Kept out of scope beyond verifying the existing picker flow still works end-to-end.

## Risks / Trade-offs

[Two mirrors can now silently share a `source`] → Any future code iterating mirrors and assuming `source` is a unique key (e.g. a lookup dict keyed by source) would silently overwrite entries. Mitigated by grep-auditing current usages of `.get("source")` as a key during implementation; none found treating it as unique besides the duplicate check itself.

[A "true duplicate" resubmission with identical candidate still needs a clear error] → Preserved by keeping the check, just narrowed to the full tuple.

## Migration Plan

No data migration. This is a pure logic relaxation in `mirror_core.py`; existing `payloads.json` records need no changes. Deploy as a normal code update.

## Open Questions

None — scope is narrow and confirmed against the existing candidate-resolution flow.
