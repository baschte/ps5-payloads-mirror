## Why

The mirror table is only ever shown in the manually curated `sort_order` sequence, so finding a specific mirror — or spotting the ones that haven't been refreshed in a long time — means scanning the whole list by eye. As the collection grows this gets slower, and a user who prefers a particular view has to re-establish it mentally on every page load.

## What Changes

- The `Payload`, `Version`, `Updated`, and `Source` column headers become clickable sort controls. Clicking a header sorts the table by that column ascending; clicking the active header again flips to descending.
- A third click on the active header clears sorting and returns the table to the manually curated order (the current `sort_order` sequence from the backend), so manual curation stays reachable without a page reload.
- The active sort column and direction are persisted in `localStorage` and restored on load, so the user's last chosen view survives reloads.
- Sorting is purely client-side and presentational: it never writes to the backend and never changes any mirror's stored `sort_order`.
- Drag-and-drop reordering is disabled while a sort is active, because dropping a row into a position that isn't the persisted order would silently rewrite `sort_order` from a view the user didn't curate. Rows stop being draggable and the grip column communicates that reordering requires clearing the sort. **BREAKING** to the current expectation that every row is always draggable.
- Sort controls are keyboard-accessible and expose the current sort state to assistive technology via `aria-sort`.

## Capabilities

### New Capabilities
- `mirror-table-sorting`: Client-side, persisted sorting of the mirror table by payload name, version, last-update date, or source, including the ordering rules per column, the asc/desc/off cycle, persistence and restore semantics, and how sorting interacts with manual reordering.

### Modified Capabilities
- `frontend-base`: The "Manual Reordering" requirement gains the condition that drag-and-drop is only available while the table is in manual order; the "Mirror List Loading and Display" requirement gains the sortable-header affordance on the table.

## Impact

- `web/src/components/PayloadTable.tsx` — headers become sort buttons; applies the active sort to the rows it renders.
- `web/src/components/PayloadRow.tsx` — `draggable` and the drag handlers become conditional on manual order.
- `web/src/App.tsx` — owns (or hosts) the sort state and passes it down; unchanged reorder handler, but it is only reachable in manual order.
- New `web/src/useSortPreference.ts` (persistence hook) and `web/src/sortPayloads.ts` (comparators), following the existing `useTheme.ts` localStorage pattern.
- No backend, API, or `payloads.json` changes; no new dependencies.
