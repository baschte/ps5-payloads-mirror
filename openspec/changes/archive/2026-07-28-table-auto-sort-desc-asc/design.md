## Context

The mirror table lives in `web/src/components/PayloadTable.tsx` and renders one `PayloadRow` per entry, in exactly the order `App.tsx` holds in its `payloads` state. That order comes from the backend, which sorts by the persisted `sort_order` field (see the `mirror-reordering` capability), and drag-and-drop reordering rewrites it through `PUT`-style bulk reorder calls from `App.handleReorder`.

The frontend is a small React 18 + TypeScript + Vite SPA with no state-management library, no table library, and no test setup. There is one existing localStorage-backed preference, the theme, implemented as the `useTheme` hook in `web/src/useTheme.ts`; it wraps every storage access in `try/catch` and treats failure as non-fatal. This change follows that precedent rather than introducing anything new.

Constraint worth naming up front: the payload list is small (tens of entries), fetched in full, and already entirely client-side. There is no pagination and no server-side query surface, so sorting has no reason to involve the backend at all.

## Goals / Non-Goals

**Goals:**

- Clicking `Payload`, `Version`, `Updated`, or `Source` sorts by that column, with an asc → desc → cleared cycle on repeated clicks of the active column.
- The chosen column and direction survive a page reload via `localStorage`.
- Sorting is presentational only: no backend call, no change to any mirror's `sort_order`.
- Version sorting behaves the way a human reads versions (`v1.10.0` above `v1.9.0`), not the way a string comparison does.
- Sorted headers are keyboard-operable and announce their state via `aria-sort`.
- Manual drag-reordering keeps working, unchanged, whenever no sort is active.

**Non-Goals:**

- Multi-column / secondary sorting chosen by the user. Ties are broken by name internally, but that isn't user-configurable.
- Filtering, searching, or pagination.
- Sorting the published `payloads.json` feed or anything else server-side; the feed order stays `sort_order`.
- Persisting the sort preference per user account or across browsers — `localStorage` is per-browser, same as the theme.
- Reconciling a sorted view into a new persisted `sort_order` (i.e. "save this sort as the order"). Explicitly out of scope; see the decision below.

## Decisions

### Sort state lives in `App`, derived order computed at render

`App` already owns `payloads` and is the only place that mutates it (add, edit, update, update-all, remove, hide, reorder). Sort state goes next to it as `{ column, direction } | null`, and the sorted array is derived with `useMemo` from `payloads` plus that state. `PayloadTable` receives both the derived rows and the sort state, and renders headers accordingly.

The alternative — keeping sort state inside `PayloadTable` — reads as more encapsulated, but it puts the display order out of reach of the component that owns the data, and it would make the "no dragging while sorted" rule invisible from `App.handleReorder`. Deriving instead of storing a sorted copy also avoids the whole class of bugs where a mutation updates `payloads` and the sorted copy silently goes stale.

`payloads` itself is never re-ordered by sorting. Clearing the sort therefore needs no refetch: the curated order was never lost.

### Persistence via a `useSortPreference` hook modeled on `useTheme`

New file `web/src/useSortPreference.ts` exposes the sort state plus a single `toggle(column)` action implementing the asc → desc → cleared cycle, and writes to `localStorage` under the key `payloadSort` in an effect. Reads happen once in the `useState` initializer, wrapped in `try/catch`, and validate the parsed shape against the known column list — an unknown column, malformed JSON, or a throwing storage API all collapse to `null` (curated order). The cleared state is stored explicitly rather than by deleting the key, so "I deliberately cleared the sort" and "I never chose one" both end up at curated order without extra ceremony.

Storing a `{column, direction}` object rather than a flat string like `"version:desc"` costs nothing and avoids a bespoke parser.

### Comparators in a separate pure module

`web/src/sortPayloads.ts` holds one comparator per column plus the `sortPayloads(payloads, sort)` entry point. Keeping it a pure function of `(list, sort)` with no React imports makes the ordering rules — which are the part of this change most likely to be wrong — readable and testable in isolation, and keeps `PayloadTable` about markup.

Shared rules applied in `sortPayloads`, not duplicated per comparator:

- **Missing values last, in both directions.** A mirror with no version or no `last_update` is not "the smallest version"; it's an absence. Sinking those to the bottom regardless of direction means flipping direction never buries the rows that have data. This is why direction is applied by negating the comparator result for present-vs-present pairs only, rather than by reversing the whole array.
- **Name as the final tiebreaker.** `Array.prototype.sort` is stable in modern engines, so ties would preserve `sort_order` — but that makes the rendered order depend on a field the user can't see while sorted. An explicit name tiebreaker is deterministic and explainable.

Per-column rules: `Payload` compares the displayed label (`title ?? name`) with `localeCompare` and `sensitivity: "base"`, matching what the row actually shows. `Version` splits on non-alphanumeric boundaries and compares numeric segments numerically, alphabetic segments with `localeCompare` — deliberately not a full semver parser, because upstream tags in this collection are not reliably semver (`v1.2`, `1.2.3b`, `20240115` all occur) and a strict parser would have to reject or mis-bucket them. `Updated` parses the timestamp with `Date.parse` and compares the numeric result, treating an unparseable value as missing. `Source` compares the raw source URL case-insensitively.

### Drag-and-drop disabled while sorted, rather than reinterpreted

When a sort is active, `PayloadRow` renders without `draggable` and without its drag handlers, and the grip cell is dimmed with a title explaining that clearing the sort re-enables reordering.

The alternative is to let the drop apply to the sorted view and translate it back into a `sort_order` sequence. That was rejected: the resulting persisted order would be the sorted order with one row moved, meaning a single drag would silently overwrite the entire curated order the user built up manually. Disabling the affordance loses a little convenience and keeps a destructive surprise off the table. A future change could add an explicit "persist this sort as the order" action, which would be honest about what it does.

### Rendering approach for headers

Each sortable `<th>` gets `aria-sort` and contains a `<button type="button">` wrapping the label and the direction indicator. Using a real button — rather than `onClick` on the `<th>` with a `tabIndex` — gets keyboard activation via Enter and Space, focus styling, and correct semantics without hand-rolling any of it. The indicator is a small chevron that is present-but-transparent on inactive columns so the header row doesn't shift horizontally when the active column changes.

## Risks / Trade-offs

- **Version comparison is heuristic, not semver** → Upstream tags are inconsistent enough that a strict parser would fail on real data. The segment-wise comparator degrades gracefully (falls back to string comparison on non-numeric segments) rather than throwing, and version sort is a browsing aid rather than a correctness-critical ordering. Documented in the module so the next reader doesn't mistake it for semver.
- **Losing drag-reorder while sorted may read as a bug** → Mitigated by the dimmed grip plus an explanatory `title`, so the state is discoverable in place rather than only in the spec.
- **A stale persisted column name after a future column rename** → The restore path validates against the current column list and falls back to curated order, so a rename degrades to "sort was forgotten once" rather than a crash.
- **Sort re-applies on every list mutation, moving a row out from under the pointer** → Real but minor: it's the correct behavior (the row's value changed, so its position should change), and the affected interactions are single-row actions that complete before the reorder is visible.
- **No test setup in `web/`** → Verification is manual for this change: exercise each column both directions, reload to confirm restore, clear and confirm both curated order and drag-reorder return. Adding a test runner is out of scope here, and `sortPayloads.ts` is deliberately shaped to be trivially testable once one exists.
