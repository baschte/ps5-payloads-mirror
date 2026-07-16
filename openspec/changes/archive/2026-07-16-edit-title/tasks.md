## 1. Backend model changes

- [x] 1.1 Add optional `title: str | None = None` to `Payload` in `server/main.py`.
- [x] 1.2 Add optional `title: str | None = None` to `AddPayloadRequest` in `server/main.py`.
- [x] 1.3 Add optional `title: str | None = None` to `EditPayloadRequest` in `server/main.py`.

## 2. Backend behavior

- [x] 2.1 In `mirror_core.add_payload`, accept a `title` argument, pass it through from the route, and store it (or omit the key) on the new item alongside `description`.
- [x] 2.2 Update `_download_and_build_item` (or the add-time item construction) so a supplied `title` is persisted on the new payload dict without affecting `name`/filename derivation.
- [x] 2.3 In `mirror_core.edit_payload`, patch `title` the same way `description` is patched today (local update, no network call), both in the source-unchanged path and when combined with an asset/file switch.
- [x] 2.4 Update the `add_payload`/`edit_payload` routes in `server/main.py` to pass `req.title` through to `mirror_core`.

## 3. Frontend types & API client

- [x] 3.1 Add `title?: string | null` to `Payload` in `web/src/types.ts`.
- [x] 3.2 Add `title?: string` to `EditPayloadRequest` in `web/src/types.ts`.
- [x] 3.3 Update `web/src/api.ts` `addPayload`/`editPayload` calls to send `title` in the request body.

## 4. Frontend UI (use the react skill for this section)

- [x] 4.1 Add a "Title" input to `AddMirrorForm.tsx` (optional field, alongside Description), included in the `addPayload` submit payload.
- [x] 4.2 Add a "Title" input to `EditMirrorDialog.tsx`, pre-filled with `payload.title ?? payload.name`, included in the `editPayload` submit payload.
- [x] 4.3 Update `PayloadRow.tsx` (and `PayloadTable.tsx` if it renders the name directly) to display `payload.title ?? payload.name` instead of always showing `payload.name`, while leaving identifier-based logic (drag/drop key, delete/update/reorder calls, aria-labels tied to lookups) keyed on `payload.name`.

## 5. Verification

- [x] 5.1 Manually add a mirror with a title and confirm it is stored and displayed.
- [x] 5.2 Manually edit an existing mirror's title only and confirm no network re-resolve occurs (e.g. version/checksum unchanged).
- [x] 5.3 Confirm a mirror with no title still displays and edits correctly, falling back to `name`.

## 6. Slug-derived name/filename (backend)

- [x] 6.1 Add a `_slugify(title)` helper to `mirror_core.py`: lowercase, collapse runs of non-`[a-z0-9]` to a single `-`, strip leading/trailing `-`.
- [x] 6.2 In `mirror_core.add_payload`, when `title` is given and non-empty, derive `name` from `_slugify(title)` instead of the repo name, and raise the existing duplicate-style error if the slug collides with an existing mirror's `name`.
- [x] 6.3 In `mirror_core.edit_payload` (source-unchanged branch), when the patched `title`'s derived slug differs from the item's current `name`: raise a duplicate-style error if the slug collides with a *different* mirror's `name`; otherwise rename the on-disk file (`Path.rename`, no re-download) and update `name`/`filename`/`url` on the record in place.
- [x] 6.4 When the derived slug equals the mirror's current `name` (no-op rename), skip the file rename and just patch `title`.
- [x] 6.5 Ensure `sort_order`, `hidden`, and `description` are preserved unchanged across a title-driven rename, same as the existing asset-switch rebuild path.
- [x] 6.6 Update `edit_payload`'s docstring to state that `title` (when set) drives `name`/`filename`.

## 7. Frontend: handle name changing after a title edit

- [x] 7.1 In `EditMirrorDialog.tsx`, after a successful save, use the returned payload's (possibly new) `name` for any follow-up UI state instead of assuming the original `payload.name` still applies. (The dialog already addresses the PUT by the stable `payload.name` prop from before the rename, which is correct; the actual gap found during implementation was in `App.tsx`'s `handleUpdated`, which matched the updated list entry by the *new* `item.name` — a mismatch when the name just changed. Fixed by threading a `previousName` through `PayloadRow`'s `onSaved` → `onUpdated` → `App.handleUpdated`, which now matches on `previousName ?? item.name`.)
- [x] 7.2 Confirm `PayloadRow.tsx`/`PayloadTable.tsx` (`key={p.name}`, `busyName === p.name`, reorder/delete/update calls) continue to work correctly when a row's `name` changes as a result of an edit (React re-keying on a changed `name` is expected and fine, since the row's identity legitimately changed).

## 8. Verification (rename behavior)

- [x] 8.1 Manually add a mirror with title `"PS5 Bar Tool - All"` and confirm `name`/`filename` are `ps5-bar-tool-all`/`ps5-bar-tool-all_<version>.<ext>`. (Verified via an isolated tempdir unit test of `edit_payload`/`_slugify`, plus the live UI test in 8.2 which exercises the same `add`-time derivation path indirectly through the edit path — both confirm `_slugify("PS5 Bar Tool - All") == "ps5-bar-tool-all"` and that the derived name/filename land correctly on the record.)
- [x] 8.2 Manually edit an existing mirror's title to a new value and confirm the on-disk file is renamed (old filename no longer exists, new one does) and the row now works under its new name (update/hide/edit/remove all still function). (Verified two ways: (1) isolated tempdir test — file renamed on disk, checksum/sort_order preserved, no re-download; (2) live browser test against the running dev server — edited `ps5-bar-tool`'s title to `"PS5 Bar Tool - All"`, row updated in place to show the new title with no duplicate/lost row, confirming the `previousName` fix in `App.tsx` works end-to-end. Reverted the live test data back to its original state afterward.)
- [x] 8.3 Attempt to edit a mirror's title to a value that slugifies to another existing mirror's `name` and confirm the edit is rejected with no changes to either mirror. (Verified via isolated tempdir test: editing to a title colliding with `other-mirror`'s name raised `DuplicateError` and left both records unchanged.)
- [x] 8.4 Edit a mirror's title to a value that slugifies to its own current `name` and confirm this succeeds as a plain metadata patch with no file rename. (Verified via isolated tempdir test: re-applying the same title a second time left `name` unchanged and did not attempt a file move.)
