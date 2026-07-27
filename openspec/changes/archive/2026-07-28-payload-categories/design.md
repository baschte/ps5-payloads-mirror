## Context

`payloads.json` is a flat-file store, read and written wholesale by `mirror_core.py` (see `load_data`/`_write_data`) and modeled loosely by FastAPI's `Payload` (`server/main.py`), which uses `model_config = {"extra": "allow"}` — extra fields round-trip even when not declared. `add_payload`, `edit_payload`, and `_download_and_build_item` build the per-item dict directly; `FIELD_ORDER` only controls key ordering on write via `reorder_item`, it isn't a validation list.

The frontend already has two independent places that build/patch a mirror's metadata locally without touching the network — `AddMirrorForm` (new mirror) and `EditMirrorDialog` (existing mirror, description/title path) — both calling `api.ts` functions that POST/PUT a plain object. Both already have an optional-text-field pattern to copy (`description`, `title`).

The external reference point is `ps5-payload-manager`'s `CUSTOM_REPOSITORIES.md`: `category` is an optional, per-item, single string field, defaulting to "Uncategorized" downstream when absent. This mirror doesn't need to reproduce that default — it just needs to emit the field (or omit it) faithfully so that consumer's own default applies.

## Goals / Non-Goals

**Goals:**

- `category` round-trips through add, edit (including clearing it), list, and the public feed, as a single optional string.
- Setting/clearing a category never triggers a network call to the mirror's upstream source — it's a local metadata patch, same tier as `description`.
- Both the add form and the edit dialog offer autocomplete suggestions drawn from categories already in use, without restricting input to that set.
- The mirror table shows the category when set.

**Non-Goals:**

- No fixed/managed category list, no category-rename-everywhere operation, no per-category color or icon.
- No dedicated `/api/categories` endpoint. The full payload list is already fetched by the app on load; deriving distinct categories from it client-side is sufficient and avoids a redundant round trip that would need its own cache-invalidation story.
- No case-normalization or fuzzy-matching of category names. "Networking" and "networking" are different categories unless the user types them the same way — consistent with `ps5-payload-manager`'s schema, which imposes no naming constraints either.
- No category filter/grouped view in this mirror's own table. Categories exist here to be *set* for downstream consumption; grouping the table itself by category is a separate, not-yet-requested feature.

## Decisions

### Backend: `category: str | None`, trimmed-to-`None`-when-empty, no new endpoint

Add `category: str | None = None` to `mirror_core`'s implicit item shape (via `FIELD_ORDER` and the two builder functions) and to `server/main.py`'s `Payload`, `AddPayloadRequest`, `EditPayloadRequest` models — mirroring exactly how `title`/`description` are declared. Trimming and empty-to-`None` collapsing happens once, at write time, the same place `description` is already `.strip()`-ed and `title` is already `.strip() or None`.

`edit_payload`'s local-patch branch (`source_unchanged`) gets one more `if category is not None: updated["category"] = category.strip() or None` line, parallel to the existing `description` line. This is deliberately a *tri-state* parameter at the API boundary: `None` (field omitted from the request) means "leave unchanged," while `""` (present but empty) means "clear it" — exactly the convention `description` doesn't currently need (it's always sent) but `title`'s optionality already relies on. Pydantic's `category: str | None = None` on `EditPayloadRequest` plus checking `is not None` gives this for free without extra fields.

No `/api/categories` endpoint: `GET /api/payloads` already returns every field on every mirror, visible and hidden, and the frontend already fetches it once on load and keeps it in `App`'s state. A second endpoint would just be a redundant view of data already in memory, and would need its own refresh timing to stay in sync with `payloads` — not worth it for a client-side `Set` computation.

### Frontend: known-categories derived once in `App`, threaded down as a plain array

`App.tsx` computes `const knownCategories = useMemo(() => distinct non-empty categories from payloads, sorted, [payloads])` and passes it to `AddMirrorForm` (new prop) and down through `PayloadTable` → `PayloadRow` → `EditMirrorDialog` (same threading pattern already used for `sort`/`onToggleSort` in the table-sorting change). Deriving it in `App` rather than in each form keeps a single source of truth and means the suggestion list updates automatically whenever `payloads` changes — no separate fetch, no staleness.

### Frontend: `<input list="…">` + `<datalist>`, not a custom combobox

HTML's native `<datalist>` gives free-text-with-suggestions for exactly zero extra JS and zero new dependencies — the browser handles matching, keyboard navigation, and dismissal. The alternative (a hand-rolled dropdown, or pulling in a combobox library) buys accessibility and cross-browser behavior this project doesn't have infrastructure to maintain, for a feature that's explicitly "suggest, don't constrain." `<datalist>`'s well-known browser inconsistencies (styling can't be touched, `list` support on `type="text"` is universal but visual affordance varies) are acceptable here because the field is genuinely free text — a user typing past the suggestions is not a degraded state, it's the intended behavior.

Each `<datalist>` gets a stable, unique `id` (`category-suggestions` on the add form, `edit-category-suggestions` in the dialog — the dialog is portal-rendered, so IDs must not collide if the form and dialog are ever visible at once) and is populated from the same `knownCategories` prop.

### Frontend: category chip next to the title, following the existing "Hidden" chip pattern

`PayloadRow` already renders a `<span className="chip …">Hidden</span>` next to the title when `payload.hidden`. The category gets the same treatment — a chip rendered conditionally when `payload.category` is set, placed after the "Hidden" chip if both are present. This was chosen over other placements (a new table column, a tooltip) because: a new column costs table width for a field that's usually absent; the existing chip slot right next to the title is exactly where a reader's eye already goes to see a mirror's status, and the pattern is already established.

## Risks / Trade-offs

- **No server-side dedup/casing on categories** → "Networking" and "networking" can coexist as different categories, which could look like a mistake to the user. Mitigated by autocomplete: as long as the suggestion list surfaces the existing spelling prominently, most users will reuse it rather than retype a variant. Not solving this in v1 keeps the field genuinely free-text, matching the upstream schema's own lack of constraints.
- **`<datalist>` styling can't be customized to match the app's design system** → Accepted; the suggestion popup is a native browser affordance here, not a designed UI surface, and it only appears while actively typing.
- **Tri-state `category: str | None` on edit (omitted vs. empty vs. value) is an implicit convention, not enforced by types** → Documented here and mirrored exactly by the existing, working `title`/`description` handling in the same function, so a future reader has a working precedent to compare against rather than a novel pattern to reverse-engineer.
