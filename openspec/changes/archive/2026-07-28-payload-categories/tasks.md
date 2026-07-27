## 1. Backend model and persistence

- [x] 1.1 In `mirror_core.py`, add `"category"` to `FIELD_ORDER` (after `description`, before `last_update`, matching the field's place in the upstream schema example).
- [x] 1.2 In `mirror_core.py`, thread `category` through `add_payload`: accept a `category` parameter, and in `_download_and_build_item`, store `"category": (category or "").strip() or None` on the built item (parallel to how `title` is handled).
- [x] 1.3 In `mirror_core.py`'s `edit_payload`, in the `source_unchanged` branch, add `if category is not None: updated["category"] = category.strip() or None` (parallel to the existing `description` line) so category can be set or cleared without a network call.
- [x] 1.4 In `mirror_core.py`'s `edit_payload`, in the source-URL-changed branch, carry over the existing category the same way `sort_order`/`hidden` are preserved, unless the request also explicitly changes it — i.e. `new_category = category if category is not None else item.get("category")`, then pass it into the rebuilt item.
- [x] 1.5 In `server/main.py`, add `category: str | None = None` to the `Payload`, `AddPayloadRequest`, and `EditPayloadRequest` models.
- [x] 1.6 In `server/main.py`'s `add_payload` and `edit_payload` route handlers, pass `req.category` through to the corresponding `mirror_core` functions.

## 2. Frontend types and API client

- [x] 2.1 In `web/src/types.ts`, add `category?: string | null` to `Payload` and to `EditPayloadRequest`.
- [x] 2.2 In `web/src/api.ts`, add `category?: string | null` to `addPayload`'s request body type and pass it through in the request.

## 3. Add mirror form

- [x] 3.1 In `App.tsx`, compute `knownCategories` via `useMemo`: the distinct, non-empty, trimmed `category` values across `payloads`, sorted case-insensitively.
- [x] 3.2 Pass `knownCategories` as a new prop to `AddMirrorForm`.
- [x] 3.3 In `AddMirrorForm.tsx`, add a `category` state field, a labeled optional text input wired to it with `list="category-suggestions"`, and a `<datalist id="category-suggestions">` populated from the `knownCategories` prop.
- [x] 3.4 Include `category: category.trim() || null` in the `addPayload` call, and reset it alongside the other fields on successful submit.

## 4. Edit mirror dialog

- [x] 4.1 Thread `knownCategories` from `App.tsx` through `PayloadTable` → `PayloadRow` → `EditMirrorDialog` as a prop.
- [x] 4.2 In `EditMirrorDialog.tsx`, add a `category` state field initialized from `payload.category ?? ""`, a labeled optional text input wired to it with `list="edit-category-suggestions"`, and a `<datalist id="edit-category-suggestions">` populated from the `knownCategories` prop.
- [x] 4.3 Include `category: category.trim() || null` in the `editPayload` call in `handleSubmit`.

## 5. Category display

- [x] 5.1 In `PayloadRow.tsx`, render a chip showing `payload.category` next to the title, after the existing "Hidden" chip, only when `payload.category` is truthy.

## 6. Verification

- [x] 6.1 Run `npm run build` (or the project's typecheck script) in `web/` and fix any type errors.
- [x] 6.2 Add a mirror with a category and confirm it's persisted: reappears after reload, is present in `GET /api/payloads` and in `/payloads.json`, and shows as a chip in the table.
- [x] 6.3 Add a mirror with no category and confirm no `category` field/chip appears, and it doesn't show up in the autocomplete suggestion list.
- [x] 6.4 Edit an existing mirror to add a category without changing its source URL, and confirm no network request to the source is made (e.g. via network inspector) and the chip updates. (Confirmed at the code level: `edit_payload`'s local-patch branch, which handles category-only edits, only reaches `get_latest_release` inside the `asset_changed or member_changed` sub-branch — untouched here — and this was exercised directly in a backend smoke test plus end-to-end through the UI.)
- [x] 6.5 Edit an existing mirror to clear its category and confirm the chip disappears and the field is absent from subsequent API responses.
- [x] 6.6 Confirm typing into the category field on both the add form and the edit dialog suggests categories already used by other mirrors, and that submitting a value not in the list is accepted.
- [x] 6.7 Confirm editing a mirror's source URL (a full re-resolve) without touching the category field leaves its existing category intact on the rebuilt record.
