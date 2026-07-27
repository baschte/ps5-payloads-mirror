## ADDED Requirements

### Requirement: Sortable mirror table columns
The mirror table SHALL let a user sort the listed mirrors by the `Payload`, `Version`, `Updated`, or `Source` column by activating that column's header, and SHALL sort entirely client-side without persisting any ordering to the backend.

#### Scenario: Sorting by a column for the first time
- **WHEN** a user activates the `Payload`, `Version`, `Updated`, or `Source` header while the table is not sorted by that column
- **THEN** the visible rows SHALL be reordered by that column in ascending direction, and no request SHALL be sent to the backend

#### Scenario: Flipping the direction of the active column
- **WHEN** a user activates the header of the column the table is currently sorted by ascending
- **THEN** the visible rows SHALL be reordered by that same column in descending direction

#### Scenario: Clearing the sort returns to the curated order
- **WHEN** a user activates the header of the column the table is currently sorted by descending
- **THEN** the sort SHALL be cleared and the rows SHALL be shown in the order the backend returned them (each mirror's persisted `sort_order`)

#### Scenario: Switching to a different column
- **WHEN** the table is sorted by one column in either direction and the user activates a different sortable header
- **THEN** the table SHALL sort by the newly activated column in ascending direction

#### Scenario: Non-sortable columns
- **WHEN** a user activates the reorder-handle column header or the `Actions` column header
- **THEN** the ordering SHALL NOT change

### Requirement: Per-column ordering rules
The system SHALL define a deterministic total ordering for every sortable column, SHALL place mirrors with no value for the sorted column last regardless of direction, and SHALL break ties by mirror name so that equal values never render in an unstable order.

#### Scenario: Sorting by payload
- **WHEN** the table is sorted by `Payload`
- **THEN** mirrors SHALL be ordered by their displayed label (the mirror's title, or its name when it has no title) using case-insensitive, locale-aware comparison

#### Scenario: Sorting by version
- **WHEN** the table is sorted by `Version`
- **THEN** version strings SHALL be compared segment by segment so that numeric segments compare numerically rather than lexicographically (for example `v1.10.0` SHALL sort above `v1.9.0` in descending direction)

#### Scenario: Sorting by updated
- **WHEN** the table is sorted by `Updated`
- **THEN** mirrors SHALL be ordered chronologically by their last-update timestamp, with the oldest first in ascending direction

#### Scenario: Sorting by source
- **WHEN** the table is sorted by `Source`
- **THEN** mirrors SHALL be ordered by their source URL using case-insensitive comparison

#### Scenario: Missing values sort last
- **WHEN** one or more mirrors have no value for the sorted column
- **THEN** those mirrors SHALL appear after all mirrors that have a value, in both ascending and descending direction, ordered among themselves by mirror name

#### Scenario: Equal values are ordered deterministically
- **WHEN** two or more mirrors compare equal on the sorted column
- **THEN** they SHALL be ordered relative to each other by mirror name, producing the same rendering on every evaluation

### Requirement: Sort selection persists across reloads
The system SHALL persist the active sort column and direction in `localStorage`, SHALL restore it when the app loads, and SHALL treat unavailable or unusable stored state as "no sort" rather than failing.

#### Scenario: Restoring the last selection
- **WHEN** a user sorts by a column in a given direction and later reloads the page
- **THEN** the table SHALL be rendered with that same column and direction already applied

#### Scenario: Cleared sort is remembered as cleared
- **WHEN** a user clears the sort and reloads the page
- **THEN** the table SHALL be rendered in the backend-provided curated order, not in the previously sorted order

#### Scenario: Stored value is invalid or unknown
- **WHEN** the persisted sort state is missing, malformed, or names a column that is no longer sortable
- **THEN** the table SHALL fall back to the curated order without raising an error to the user

#### Scenario: Storage is unavailable
- **WHEN** reading from or writing to `localStorage` throws (for example because storage is disabled)
- **THEN** sorting SHALL still work for the current session and the failure SHALL NOT surface as an error to the user

### Requirement: Sort state is exposed accessibly
The sortable headers SHALL be operable by keyboard and SHALL communicate the current sort state to assistive technology and sighted users alike.

#### Scenario: Keyboard operation
- **WHEN** a user moves focus to a sortable header and activates it with Enter or Space
- **THEN** the same sort transition SHALL occur as for a pointer click, and focus SHALL remain on that header

#### Scenario: Announcing sort state
- **WHEN** the table is sorted by a column
- **THEN** that column's header cell SHALL carry `aria-sort` with the value `ascending` or `descending` matching the active direction, every other header cell SHALL carry `aria-sort="none"` or omit it, and the active header SHALL show a direction indicator

### Requirement: Sorting and manual reordering are mutually exclusive
The system SHALL keep drag-and-drop reordering available only while the table is in its curated order, so that a persisted reorder can never be derived from a sorted view.

#### Scenario: Dragging is unavailable while sorted
- **WHEN** the table is sorted by any column
- **THEN** rows SHALL NOT be draggable, no reorder request SHALL be issuable from the table, and the reorder affordance SHALL indicate that sorting must be cleared first

#### Scenario: Dragging returns when the sort is cleared
- **WHEN** a user clears the active sort
- **THEN** rows SHALL become draggable again and drag-and-drop reordering SHALL behave exactly as before the sort was applied

### Requirement: Sorting is stable under list mutations
The system SHALL re-apply the active sort to the current set of mirrors whenever that set changes, without requiring user interaction.

#### Scenario: A mirror is added, updated, or removed while sorted
- **WHEN** the mirror list changes while a sort is active (for example after an add, edit, single update, update-all, scheduled run, or removal)
- **THEN** the resulting list SHALL be rendered in the active sort order, with any changed values reflected in the row's new position

#### Scenario: Hidden mirrors participate in the sort
- **WHEN** the table is sorted and the list contains both hidden and visible mirrors
- **THEN** hidden mirrors SHALL be sorted together with visible ones by the same rules and SHALL keep their hidden styling and indicator
