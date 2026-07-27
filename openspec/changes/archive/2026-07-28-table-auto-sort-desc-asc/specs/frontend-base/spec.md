## MODIFIED Requirements

### Requirement: Mirror List Loading and Display
The frontend SHALL fetch the list of mirrored payloads on load and render them in a table, showing a loading state while the initial fetch is in flight and an empty state when there are none. The table's `Payload`, `Version`, `Updated`, and `Source` headers SHALL act as sort controls, as specified by the `mirror-table-sorting` capability.

#### Scenario: Initial load
- **WHEN** the app mounts
- **THEN** it fetches the payload list and the collection title, showing a loading placeholder until the payload list request resolves

#### Scenario: Empty mirror list
- **WHEN** the fetched payload list is empty
- **THEN** the table area renders an empty-state message instead of a table

#### Scenario: Load failure
- **WHEN** the initial payload list fetch fails
- **THEN** an error toast is shown with the failure message (or a generic fallback if the error has no message)

#### Scenario: Rows are rendered in the active order
- **WHEN** the payload list is rendered
- **THEN** rows appear in the active sort order if a sort is active, and otherwise in the order returned by the backend

### Requirement: Manual Reordering
The frontend SHALL allow reordering mirrors via drag-and-drop while the table is in its curated (unsorted) order, applying the change optimistically and reverting on failure. While a column sort is active, drag-and-drop reordering SHALL be unavailable.

#### Scenario: Successful reorder
- **WHEN** a user drags a mirror row and drops it onto another row's position
- **THEN** the local list order updates immediately, the reorder API is called with the full new name order, and the optimistic order is kept once the API confirms success

#### Scenario: Failed reorder
- **WHEN** the reorder API call fails after an optimistic reorder
- **THEN** the list reverts to its pre-drag order and an error toast is shown

#### Scenario: Reordering while a sort is active
- **WHEN** the table is sorted by a column
- **THEN** rows are not draggable, no reorder API call can be triggered from the table, and the reorder affordance indicates that the sort must be cleared to reorder manually
