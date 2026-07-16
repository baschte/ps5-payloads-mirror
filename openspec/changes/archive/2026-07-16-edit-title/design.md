## Context

Each mirror's `name` is derived once at add-time from the source repo (see
`_download_and_build_item` in `mirror_core.py`) and then reused everywhere:
as the display label, the filename prefix on disk, and the unique key used
by every lookup (`edit_payload(name, ...)`, delete, update, reorder,
candidate-listing). It is never user-editable today.

The user wants a `title` field to also drive `name` (and thus `filename`,
and the asset name uploaded to the GitHub release): setting a title fully
renames the entry, not just its display label.

## Goals / Non-Goals

**Goals:**
- Let a user set/change a human-facing title when adding or editing a mirror.
- When a title is set/changed, derive `name` from it via a slug rule, rename
  the on-disk file to match, and persist both under the mirror's existing
  list position.
- Reject a title edit whose derived slug collides with a *different*
  existing mirror's `name`, leaving that mirror's record and file untouched.
- Keep entries with no title unaffected: they keep their current `name`
  (derived from the repo, as today) until a title is set.

**Non-Goals:**
- Any change to how `name` is derived from the source repo when no title is
  given — that path (repo name → `name`) stays exactly as-is.
- Changing the *lookup* mechanism itself: routes still take `name` in the
  URL/path; a title-driven rename changes what that `name` *is*, not how
  it's looked up.
- Any GitHub Actions workflow change — `update_mirror.yml` uploads
  `payloads/*` by on-disk filename already, so a renamed file is picked up
  automatically on the next run.

## Decisions

- **`name` becomes derived from `title` when a title is present, otherwise
  unchanged from today's repo-derived value.** Rather than introducing a
  second identifier, `title` becomes the source of truth for `name` once
  set, matching the user's ask that name/filename/release-asset all track
  the title. The rename happens only as a side effect of an explicit title
  change (add-time, or an edit that changes `title`) — never spontaneously.
- **Slug rule**: lowercase, collapse every run of non-`[a-z0-9]` characters
  to a single `-`, strip leading/trailing `-`. Implemented as a small pure
  helper (`_slugify(title)`) in `mirror_core.py`, reused by both
  `add_payload` and `edit_payload`.
- **Rename is folded into the existing rebuild path.** `edit_payload`
  already has a branch that rebuilds `filename`/downloads when
  `asset_name`/`extract_file` change (via `_download_and_build_item`) and
  removes the old file from disk. A title change reuses the same "compute
  new filename, move the file, update the record in place" shape — except
  no re-download is needed, since the underlying asset bytes are unchanged;
  it's a rename of the existing file on disk (`Path.rename`), then a patch
  of `name`/`filename`/`url`/`title` on the stored record at its current
  list index.
- **Duplicate-slug check mirrors duplicate-source.** Before renaming,
  `edit_payload` checks the derived slug against every *other* mirror's
  `name` (excluding the item being edited itself, same exclusion the
  duplicate-source check already uses) and raises the same `DuplicateError`
  family if it collides, without touching the file or record.
- **Title-only edits without a name change still short-circuit to a plain
  patch.** If the newly derived slug equals the mirror's current `name`
  (e.g. title changed in a way that slugifies the same, or title is set but
  unchanged), no rename/file-move happens — just a metadata patch, same as
  a `description`-only edit today.
- **Fallback to `name` for display, not a stored default.** `title` is
  stored as `None`/absent unless the user sets it, and every read path
  (API model default, frontend display) falls back to `name` when absent.

## Risks / Trade-offs

- [**BREAKING**: `name` is no longer stable once a mirror has a title — any
  external consumer that bookmarks a mirror by `name` (e.g. a direct link to
  `/api/payloads/{name}`) breaks when the title changes] → accepted per the
  user's explicit request; called out as a breaking change in the proposal.
  `source` (the upstream repo URL) remains the actual stable identity of a
  mirror across a rename.
- [A client mid-edit (e.g. the Edit dialog) references the mirror by its
  *old* `name` in the request URL; if the same mirror was renamed by another
  concurrent request first, the edit 404s] → same race window that already
  exists for any concurrent edit of the same mirror today (serialized by
  `DATA_LOCK`, but a stale client-side URL isn't); not newly introduced by
  this change, so no additional mitigation beyond the existing lock.
- [Renaming can collide with the *new* filename already existing on disk
  from a previous run] → the rename path unlinks/overwrites the destination
  the same way the existing asset-switch rebuild path already does when
  `old_filename != new_filename`.
- [Two similarly-named fields (`name`, `title`) could still confuse future
  contributors, now that `name` is derived rather than purely automatic] →
  mitigated by a docstring on `edit_payload`/`_slugify` stating the
  derivation rule and that `title` (when set) is the source of truth.
