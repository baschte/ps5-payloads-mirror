## Why

The mirrors table has no manual ordering — the on-disk order is whatever
`_write_data` computes by sorting on `last_update`, so it silently reshuffles
on every save (add, edit, update, scheduled run). There is also no way to
temporarily take a mirror out of the published feed/README without deleting
it outright — removing a mirror discards its record entirely, with no path
back except re-adding it from scratch.

## What Changes

- Add a `sort_order` (integer) field to every payload item. It becomes the
  sole ordering key for both the stored file(s) and the API response,
  replacing the current auto-sort-by-`last_update` in `_write_data`.
  New mirrors are appended with `sort_order = max(existing) + 1`.
- Add a drag-and-drop UI for the mirrors table (native HTML5 Drag and Drop
  API — no new frontend dependency) that lets a user manually reorder rows.
  On drop, the frontend sends the complete new name ordering to a new bulk
  endpoint (`PUT /api/payloads/reorder`), which recomputes and persists
  `sort_order` for every affected item in one write.
- Add a `hidden` (boolean) field and a hide/show toggle per mirror. Hiding a
  mirror moves its full record out of the tracked, git-committed
  `payloads.json` into a new file, `hidden_payloads.json`, that lives only
  on the local filesystem/container and is **never** committed, pushed, or
  touched by the existing git auto-publish mechanism. Showing it again moves
  the record back. Hidden and visible items share the same `sort_order`
  numbering space, so the UI can render them in one continuous, manually
  reorderable list — hidden rows are simply styled differently (dimmed, a
  "Hidden" badge), not moved to a separate section or tab.
- Hidden mirrors are **not** paused: the scheduler and "update all" continue
  to check and refresh hidden mirrors' files/version/checksum in the
  background exactly as before. Hiding is purely a visibility/publishing
  concern.
- Internally, `load_data()`/`save_payloads()` keep a single shared pipeline:
  they transparently read/merge both files into one list (tagged with
  `hidden`) and split back into the two files on write, based on each item's
  `hidden` flag. All existing mutating operations (`add_payload`,
  `edit_payload`, `update_one`, `update_all`, `remove_payload`) keep operating
  on "the list" unchanged — no dual code paths.
- `docker-compose.yml`'s bind mount is extended to ensure `hidden_payloads.json`
  persists across container rebuilds the same way `payloads.json` does today.
  `.gitignore` gets a new entry for it.
- **BREAKING (internal only)**: `_write_data`'s automatic sort-by-`last_update`
  is removed. Existing `payloads.json` entries have no `sort_order` yet; the
  first write after this ships assigns one based on each item's current
  position (see design.md for the exact migration).

## Capabilities

### New Capabilities

- `mirror-reordering`: Manual, persisted, drag-and-drop-driven ordering of
  mirrors via a `sort_order` field and a bulk reorder endpoint, replacing
  the previous automatic sort-by-`last_update`.
- `mirror-visibility`: Hiding and showing a mirror without deleting it,
  backed by a separate, non-git-tracked file, with automatic updates
  continuing to run for hidden mirrors.

### Modified Capabilities

- `mirror-editing`: The "Edit an existing mirror's source URL" requirement
  (in-place replacement of a mirror's fields "at its current position in the
  payload list") is affected by the introduction of `sort_order` as the
  ordering key and `hidden` as a file-placement key. A URL-changing edit
  must now explicitly carry over the edited item's existing `sort_order` and
  `hidden` value onto the rebuilt item — otherwise editing a mirror's source
  would silently reset its manually-chosen position or move it between
  `payloads.json`/`hidden_payloads.json`. This is a behavior clarification of
  an existing requirement, not a new one.

## Impact

- **Backend (`mirror_core.py`)**: new `HIDDEN_JSON_FILE` path constant;
  `load_data()` reads and merges both files; `save_payloads()`/`_write_data()`
  split items by `hidden` and write two files, ordering both by `sort_order`
  instead of `last_update`; new `reorder_payloads(names_in_order)` function;
  `add_payload` assigns `sort_order` on creation; `edit_payload`'s in-place
  replacement path preserves the edited item's `sort_order`/`hidden`; a
  one-time `sort_order` backfill for pre-existing entries with none.
- **Backend (`server/main.py`)**: new `PUT /api/payloads/reorder` endpoint;
  new endpoint (or extended `PUT /api/payloads/{name}`) to toggle `hidden`.
- **Backend (`server/git_ops.py`)**: `COMMIT_FILES` must continue to exclude
  `hidden_payloads.json` (it already only lists `payloads.json`/`README.md`,
  so no change needed there, but this is called out for verification).
- **Deployment**: `docker-compose.yml` bind mount and `.gitignore` updated so
  `hidden_payloads.json` persists locally but is never committed/published.
- **Frontend (`web/src/api.ts`)**: new `reorderPayloads()` and a hide/show
  call.
- **Frontend (`web/src/components/`)**: `PayloadRow.tsx` becomes draggable
  (native HTML5 DnD) with a hide/show toggle button and hidden-state styling;
  `PayloadTable.tsx`/`App.tsx` manage optimistic reorder state and roll back
  on failure.
- **Frontend (`web/src/types.ts`)**: `Payload` gains `sort_order` and
  `hidden` fields.
