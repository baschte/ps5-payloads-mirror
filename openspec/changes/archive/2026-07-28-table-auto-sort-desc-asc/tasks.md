## 1. Sorting core

- [x] 1.1 Create `web/src/sortPayloads.ts` with the exported `SortColumn` union (`"payload" | "version" | "updated" | "source"`), `SortDirection` (`"asc" | "desc"`), a `SortState` type (`{ column: SortColumn; direction: SortDirection }`), and a `SORT_COLUMNS` array used for both header rendering and persistence validation.
- [x] 1.2 Implement the per-column value extractors: displayed label (`title ?? name`) for `payload`, `version`, parsed `Date.parse(last_update)` for `updated`, and `source` — each returning `null` when the value is absent, empty, or (for `updated`) unparseable.
- [x] 1.3 Implement the segment-wise version comparator: split on non-alphanumeric boundaries, compare numeric segments numerically and alphabetic segments with `localeCompare`, shorter-prefix-first on a tie. Add a short comment noting it is deliberately heuristic, not semver.
- [x] 1.4 Implement `sortPayloads(payloads, sort)`: returns the input array unchanged when `sort` is `null`; otherwise sorts a copy, sinking rows with a `null` extracted value below all rows with a value in both directions, applying `direction` only to present-vs-present comparisons, and breaking every remaining tie by `name`.

## 2. Persisted preference

- [x] 2.1 Create `web/src/useSortPreference.ts` following the `useTheme.ts` pattern: `useState` initializer reads `localStorage` key `payloadSort` inside `try/catch`, `JSON.parse`s it, and validates `column` against `SORT_COLUMNS` and `direction` against the two allowed values — anything else yields `null`.
- [x] 2.2 Add the persisting effect that writes the current state (including the explicit cleared state) back to `payloadSort`, swallowing storage errors as non-fatal.
- [x] 2.3 Expose a `toggle(column)` action implementing the cycle: inactive column → that column ascending; active + ascending → descending; active + descending → cleared (`null`).

## 3. Table wiring

- [x] 3.1 In `App.tsx`, consume `useSortPreference`, derive the rendered list with `useMemo(() => sortPayloads(payloads, sort), [payloads, sort])`, and pass the derived list plus `sort` and `toggle` to `PayloadTable`. Leave `payloads` itself unsorted so clearing the sort restores the curated order without a refetch.
- [x] 3.2 In `PayloadTable.tsx`, accept the new `sort` and `onToggleSort` props and render `Payload`, `Version`, `Updated`, and `Source` headers as `<button type="button">` inside their `<th>`, leaving the reorder-handle and `Actions` headers non-interactive.
- [x] 3.3 Set `aria-sort` on each sortable `<th>` — `"ascending"`/`"descending"` on the active column, `"none"` elsewhere — and render a chevron indicator that is present but transparent on inactive columns so the header row does not shift when the active column changes.
- [x] 3.4 Pass a `sortActive` (or equivalent) flag from `PayloadTable` to each `PayloadRow`.

## 4. Reorder interaction

- [x] 4.1 In `PayloadRow.tsx`, make `draggable` and all drag handlers (`onDragStart`, `onDragEnd`, `onDragOver`, `onDragLeave`, `onDrop`) conditional on the sort being inactive, so no reorder can originate from a sorted view.
- [x] 4.2 Dim the grip cell and drop its grab cursor while sorted, with a `title` explaining that clearing the sort re-enables manual reordering.
- [x] 4.3 Confirm `App.handleReorder` needs no change and cannot be reached while sorted, since the table is the only caller.

## 5. Verification

- [x] 5.1 Run `npm run build` (or the project's typecheck script) in `web/` and fix any type errors.
- [x] 5.2 With the dev server running, sort by each of the four columns in both directions and confirm the ordering matches the spec — including that mirrors with no version, no update timestamp, or no source sink to the bottom in both directions.
- [x] 5.3 Confirm the asc → desc → cleared cycle on the active header, that switching columns starts at ascending, and that clearing restores the exact backend order.
- [x] 5.4 Reload the page with a sort active and confirm it is restored; clear the sort, reload, and confirm the curated order is shown.
- [ ] 5.5 Confirm keyboard operation: Tab to a header, activate with Enter and Space, and verify focus stays on the header and `aria-sort` updates. (Real `<button>` elements fire `click` on Enter/Space natively in every browser; this specific check could not be exercised through the automated browser harness used for this session's verification — its synthetic key events don't trigger native button activation — so it needs a quick manual pass.)
- [x] 5.6 Confirm drag-and-drop is unavailable while sorted and works exactly as before once the sort is cleared.
- [x] 5.7 Confirm the sort re-applies automatically after an add, single update, update-all, hide/show, and remove, and that hidden mirrors sort alongside visible ones while keeping their hidden styling.
