## 1. Data model (`mirror_core.py`)

- [x] 1.1 Add `HIDDEN_JSON_FILE = BASE_DIR / "hidden_payloads.json"` constant.
- [x] 1.2 Extend `load_data()` to read both `payloads.json` and
      `hidden_payloads.json`, tag each item's `hidden` field accordingly
      (default `False` for items from `payloads.json` missing the field),
      merge into one list, backfill any missing `sort_order` based on each
      item's current position, and sort the merged list by `sort_order`.
- [x] 1.3 Update `_write_data`/`save_payloads` to partition the incoming
      list by `item["hidden"]`, writing visible items to `payloads.json` and
      hidden items to `hidden_payloads.json` (both atomically, same
      temp-file + `os.replace` pattern as today), ordered by `sort_order`
      instead of `last_update`.
- [x] 1.4 Update `FIELD_ORDER`/`reorder_item` to include `sort_order` and
      `hidden` in the canonical key order.
- [x] 1.5 Update `update_readme()` to read only visible items (i.e. items
      with `hidden` falsy) when building the README table.

## 2. Sort order on create/edit (`mirror_core.py`)

- [x] 2.1 `add_payload`: assign `sort_order = max(existing sort_order,
      default -1) + 1` to the new item.
- [x] 2.2 `edit_payload`'s URL-changed branch: carry over the edited item's
      existing `sort_order` and `hidden` onto the rebuilt item before
      replacing it in the list (per design.md Decision 6 / the
      `mirror-editing` MODIFIED requirement).
- [x] 2.3 Verify `edit_payload`'s metadata-only (source-unchanged) branch
      already preserves `sort_order`/`hidden` (it copies the existing dict),
      and add a regression check/comment confirming this.

## 3. Bulk reorder (`mirror_core.py` + `server/main.py`)

- [x] 3.1 Add `reorder_payloads(names_in_order)` to `mirror_core.py`:
      validate the given name list exactly matches the current set of known
      mirror names (visible + hidden combined) — reject with `MirrorError`
      on any mismatch (missing, extra, or duplicate names); otherwise assign
      `sort_order` in step increments (e.g. 10, 20, 30, ...) following the
      given order and persist via the existing write path.
- [x] 3.2 Add `PUT /api/payloads/reorder` in `server/main.py` accepting
      `{names: list[str]}`, calling `reorder_payloads` under `DATA_LOCK`,
      returning the updated full merged list (visible + hidden).

## 4. Hide/show toggle (`mirror_core.py` + `server/main.py`)

- [x] 4.1 Add a `set_hidden(name, hidden)` function to `mirror_core.py`:
      look up the item by name (across the merged list), set its `hidden`
      field, and persist via the existing write path (which will move it
      between files as needed).
- [x] 4.2 Add an endpoint (e.g. `PUT /api/payloads/{name}/hidden` accepting
      `{hidden: bool}`) in `server/main.py` calling `set_hidden` under
      `DATA_LOCK`.

## 5. Update paths operate over the merged list (`mirror_core.py`)

- [x] 5.1 Verify `update_all()`/`update_one()` iterate over the full merged
      list (visible + hidden) — since `load_payloads()`/`load_data()` are
      already extended in Task 1, confirm no additional filtering is
      accidentally applied that would skip hidden items.
- [x] 5.2 Verify `remove_payload` looks up and removes an item regardless of
      which file it currently lives in (i.e. operates on the merged list
      before the file-split write).

## 6. Deployment

- [x] 6.1 Add `hidden_payloads.json` to `.gitignore`.
- [x] 6.2 Confirm `server/git_ops.py`'s `COMMIT_FILES` is NOT changed to
      include `hidden_payloads.json` — add a code comment there explaining
      why it must stay excluded, to prevent a future accidental addition.
- [x] 6.3 Confirm `docker-compose.yml`'s existing whole-repo bind mount
      (`.:/app`) already covers `hidden_payloads.json` persisting across
      rebuilds; update its comments to mention the new file if useful, no
      functional change expected.

## 7. Frontend types & API client

- [x] 7.1 Add `sort_order: number` and `hidden: boolean` to the `Payload`
      type in `web/src/types.ts`.
- [x] 7.2 Add `reorderPayloads(names: string[])` to `web/src/api.ts` calling
      `PUT /api/payloads/reorder`.
- [x] 7.3 Add `setPayloadHidden(name: string, hidden: boolean)` to
      `web/src/api.ts` calling the new hide/show endpoint.

## 8. Frontend drag-and-drop UI

- [x] 8.1 Make `PayloadRow.tsx` draggable using the native HTML5 Drag and
      Drop API (`draggable`, `onDragStart`, `onDragOver`, `onDrop`), with a
      drag-handle affordance (e.g. a grip icon) and local (row-scoped)
      `useState` for transient "being dragged" / "drop target" visual state
      — not lifted to `App.tsx` or any shared store.
- [x] 8.2 `PayloadTable.tsx` renders rows directly in the order of the
      `payloads` prop (already `sort_order`-ordered from the API) with no
      separate client-side reordering state computed via `useEffect`.
- [x] 8.3 In `App.tsx`, wire the drop handler to optimistically reorder the
      local `payloads` state via a functional `setState` update immediately,
      then fire `reorderPayloads()` in the background; on failure, revert to
      the previous order and show an error toast.

## 9. Frontend hidden styling & toggle

- [x] 9.1 Add a hide/show toggle button (eye icon) to `PayloadRow.tsx`,
      calling `setPayloadHidden` and updating local state on success.
- [x] 9.2 Style hidden rows distinctly within the same table (dimmed
      opacity, a "Hidden" badge) rather than moving them to a separate
      section or tab.

## 10. Verification

- [x] 10.1 Manually verify: dragging a row to a new position persists after
      a page reload, and survives an unrelated save (e.g. "Update all").
- [x] 10.2 Manually verify: a pre-existing mirror with no `sort_order`
      (from before this change) gets one backfilled on first load, matching
      its prior position.
- [x] 10.3 Manually verify: hiding a mirror removes it from `payloads.json`,
      adds it to `hidden_payloads.json`, and it disappears from
      `/payloads.json` and the README, but still appears (dimmed) in the
      authenticated UI's mirror list.
- [x] 10.4 Manually verify: reactivating a hidden mirror moves it back to
      `payloads.json` and it reappears in the public feed/README.
- [x] 10.5 Manually verify: "Update all" / scheduled run still downloads
      updates for a hidden mirror.
- [x] 10.6 Manually verify: `git status` never shows `hidden_payloads.json`
      as untracked-but-stageable in a way that a publish operation would
      pick up (confirm `.gitignore` entry works and `git_ops.commit_and_push`
      only ever touches `payloads.json`/`README.md`).
- [x] 10.7 Manually verify: editing a hidden or manually-reordered mirror's
      source URL preserves its `sort_order` and `hidden` status.
- [x] 10.8 Manually verify: a reorder request with a mismatched name set
      (missing/extra/duplicate) is rejected and changes nothing.
