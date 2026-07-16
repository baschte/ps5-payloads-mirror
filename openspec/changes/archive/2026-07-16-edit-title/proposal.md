## Why

Every mirror's displayed name is currently just the source repo's name,
derived automatically and non-editable. Users adding or editing a mirror
have no way to give an entry a more readable or distinct title (e.g.
disambiguating two mirrors from repos that happen to share a name, or
just using clearer wording than the raw repo name).

Beyond just a display label, the user wants the mirror's `name` (and
therefore its on-disk `filename`, and the file as uploaded to the GitHub
release) to be *derived from* the title, so a custom title fully renames
the entry everywhere it surfaces — not just in the UI.

## What Changes

- Add an optional `title` field to the payload model, stored alongside
  `name`.
- When `title` is not set, the UI and any consumer fall back to displaying
  `name`, so existing entries need no migration and no backfill.
- `POST /api/payloads` (add mirror) accepts an optional `title` in the
  request body. When given, `name` is derived from it (slugified) instead
  of from the repo name, and stored on the new mirror.
- `PUT /api/payloads/{name}` (edit mirror) accepts an optional `title` in
  the request body:
  - The stored `title` is patched like `description` — no network
    re-resolve triggered by the title change itself.
  - **When the title changes, `name` (and thus `filename`) is re-derived
    from the new title via the same slug rule as add**, the on-disk file
    is renamed to match, and `payloads.json` is rewritten with the new
    `name`/`filename` at the same list position. This is a **BREAKING**
    change to the meaning of `name`: it is no longer a stable identifier
    once a mirror has a title — it changes whenever the title changes.
  - **Slug collision**: if the derived slug matches a *different* existing
    mirror's `name`, the edit is rejected the same way a duplicate source
    is rejected today (existing record and file are left untouched).
- The React "Add mirror" form (`AddMirrorForm`) gains a "Title" input.
- The React "Edit mirror" dialog (`EditMirrorDialog`) gains a "Title" input,
  pre-filled with the mirror's current title (or its `name`, if untitled).
  Saving with a changed title now also changes which URL/name the mirror is
  addressed by going forward (the dialog is keyed by the mirror's *current*
  name at the time Save is clicked, so the request still resolves correctly
  even though the name changes as a result).
- The payload table/row display the `title` (falling back to `name`) instead
  of always showing `name`.
- No GitHub Actions workflow change is needed: `update_mirror.yml` uploads
  release assets by globbing `payloads/*` and relies on the on-disk filename
  as the asset name — since `filename` is derived from `name` exactly as it
  is today, a renamed file is picked up and uploaded under its new name
  automatically on the next scheduled/triggered run.

### Slug rule (title → name)

Lowercase the title, replace every run of characters outside `[a-z0-9]`
with a single `-`, then strip leading/trailing `-`. Example:
`"PS5 Bar Tool - All"` → `"ps5-bar-tool-all"`.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `mirror-editing`: editing a mirror now also accepts and patches an
  optional `title` field; when the title changes, `name`/`filename` are
  re-derived and the on-disk file is renamed, with duplicate-slug rejection
  mirroring the existing duplicate-source check.
- `mirror-management-api`: the add-mirror request/response and the payload
  shape returned by list/add/edit now include an optional `title` field,
  and `name` is derived from `title` (when given) rather than always from
  the repo name.

## Impact

- Backend: `server/main.py` (`Payload`, `AddPayloadRequest`,
  `EditPayloadRequest` models, `add_payload`/`edit_payload` routes),
  `mirror_core.py` (`add_payload`, `edit_payload`, `_download_and_build_item`,
  new slugify helper, file-rename-on-title-change logic).
- Frontend: `web/src/types.ts` (`Payload`, `EditPayloadRequest`), `web/src/api.ts`,
  `web/src/components/AddMirrorForm.tsx`, `web/src/components/EditMirrorDialog.tsx`,
  `web/src/components/PayloadRow.tsx` / `PayloadTable.tsx` (display).
- Data: `payloads.json` — existing entries gain no new required field;
  `title` is optional and absent entries keep their current `name` until
  a title is set. Setting/changing a title on an existing entry changes its
  `name`/`filename` at that point (no bulk migration).
- CI: no change needed — `.github/workflows/update_mirror.yml` uploads
  `payloads/*` by filename, which already reflects the (possibly renamed)
  mirror name.
