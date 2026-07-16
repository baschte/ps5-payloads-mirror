## Why

Adding a mirror currently rejects any source URL that already has a mirror, full stop — even when the user explicitly wants a *second* mirror from the same releases page pointing at a different asset or ZIP-extracted file. A releases page frequently ships several distinct payload files (e.g. multiple `.elf`/`.bin` variants); today only one of them can ever be mirrored per repo. The user hit this directly trying to add a second file from `chibsaabji/ps5-bar-tool`'s releases and got `A payload from https://github.com/chibsaabji/ps5-bar-tool/releases already exists.` with no way to proceed, even though a different asset was requested.

## What Changes

- Relax the add-mirror duplicate check so it only rejects a request when it resolves to the **same source URL AND the same selected candidate** (asset name + extracted member name) as an existing mirror. Different assets/files from the same source are allowed to coexist as separate mirrors.
- **BREAKING**: Multiple stored mirrors may now share the same `source` value. Any code or UI that assumed `source` was unique per mirror (e.g. using it as a de-facto key) must key off `name` instead.
- When an add request's source+candidate combination is genuinely a duplicate, the rejection message is clarified to mention the specific asset/file, not just the source URL.
- Frontend (`AddMirrorForm`): when the initial add attempt is rejected because the release has multiple candidates but the user hasn't chosen one yet, surface the candidate picker as today; additionally, if a same-source-different-asset situation is detected without an explicit chosen candidate, prompt the user to pick a candidate rather than failing outright with a plain duplicate error.
- No change to the edit-mirror duplicate check's intent: editing still must not let one mirror's edit collide with *another* mirror's exact source+candidate pair.

## Capabilities

### Modified Capabilities
- `mirror-management-api`: "Add a mirror" requirement's duplicate-source scenario changes from "any existing mirror with the same source" to "an existing mirror with the same source AND the same resolved candidate (asset/member)". The "Edit a mirror" duplicate-source check changes the same way.

## Impact

- `mirror_core.py`: `add_payload` (duplicate check around line 767) and `edit_payload` (duplicate checks around lines 892-961) need to compare `(source, asset_pattern, extract_file)` instead of just `source`.
- `server/main.py`: no route changes; error message content only.
- `web/src/components/AddMirrorForm.tsx`: minor UX adjustment so a duplicate-source-but-different-asset case guides the user toward picking a candidate instead of a dead-end error.
- `payloads.json` schema/data: no migration needed — existing records are unaffected; the constraint that's relaxed was purely a write-time guard, not a stored field.
