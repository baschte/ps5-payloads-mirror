## Why

Downstream consumers of the public feed — notably [ps5-payload-manager](https://github.com/itsPLK/ps5-payload-manager), whose `CUSTOM_REPOSITORIES.md` documents an optional per-payload `category` field used to group payloads in its own frontend — read `category` off each item in a custom-repository JSON feed. This mirror's `payloads.json` doesn't carry that field at all today, so every mirror served from here lands in that consumer's default "Uncategorized" bucket regardless of what it actually is. Adding the field, and a way to set it from this project's own UI, lets a user group their mirrors meaningfully for anyone consuming the feed downstream.

## What Changes

- A new optional `category` field, a single free-text string per mirror (never more than one category per mirror), is added to the stored mirror record and included in `/api/payloads` and the public `/payloads.json` feed — matching the field name and semantics documented in `ps5-payload-manager`'s custom-repository schema.
- The "Add mirror" form gains a `Category` input, optional, that can be left blank.
- The "Edit mirror" dialog gains the same `Category` input, pre-filled with the mirror's current category, editable and clearable independently of every other field (no network call to the source, matching how `description`/`title` are already edited locally).
- Both inputs offer type-ahead suggestions drawn from the categories already in use across the current mirror list, so a user naming a mirror into an existing group doesn't have to remember or retype it exactly.
- The mirror table shows a small category chip next to each mirror's title when it has one, so a previously set category stays visible without opening the edit dialog.
- No fixed category list is enforced anywhere — categories are exactly what the user types, created implicitly by being used.

## Capabilities

### New Capabilities
- `payload-categories`: Setting, editing, clearing, and displaying a single free-text category per mirror, plus autocomplete suggestions sourced from categories already in use.

### Modified Capabilities
- `mirror-management-api`: The add and edit mirror requirements gain an optional `category` field; the list/feed requirements now include `category` among the persisted fields returned.
- `mirror-editing`: The existing "edit metadata without re-resolving the source" requirement extends to cover `category` alongside `description`.
- `frontend-base`: The "Add Mirror" and "Edit Mirror" requirements gain the category input and its autocomplete suggestions; the mirror list display requirement gains the category chip.

## Impact

- `mirror_core.py` — `Payload`-shaped dict gains `category`; `FIELD_ORDER`; `add_payload`/`_download_and_build_item`/`edit_payload` accept and persist it.
- `server/main.py` — `Payload`, `AddPayloadRequest`, `EditPayloadRequest` models gain `category: str | None`.
- `web/src/types.ts` — `Payload` and `EditPayloadRequest` gain `category?: string | null`.
- `web/src/api.ts` — `addPayload` request body gains `category`.
- `web/src/components/AddMirrorForm.tsx`, `web/src/components/EditMirrorDialog.tsx` — new Category field with a `<datalist>`-backed autocomplete.
- `web/src/components/PayloadRow.tsx` — category chip next to the title.
- `web/src/App.tsx` — derives the known-categories list from the loaded `payloads` and passes it down; no new API endpoint needed since the list is already fully loaded client-side.
- No new dependencies; no database or migration concerns (flat-file JSON, field is simply absent on existing records until set).
