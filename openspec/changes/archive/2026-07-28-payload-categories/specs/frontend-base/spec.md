## MODIFIED Requirements

### Requirement: Mirror List Loading and Display
The frontend SHALL fetch the list of mirrored payloads on load and render them in a table, showing a loading state while the initial fetch is in flight and an empty state when there are none. The table's `Payload`, `Version`, `Updated`, and `Source` headers SHALL act as sort controls, as specified by the `mirror-table-sorting` capability. Each row SHALL display the mirror's category, when it has one, as specified by the `payload-categories` capability.

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

### Requirement: Add Mirror
The frontend SHALL provide a form to add a new mirror from a release URL, with an optional description and an optional category, and SHALL support resolving ambiguous releases by letting the user pick a candidate asset. The category input SHALL suggest categories already in use across the current mirror list as the user types.

#### Scenario: Successful add
- **WHEN** a user submits a valid release URL (and optional description and category)
- **THEN** the app calls the add-payload API, and on success clears the form and adds the new payload to the visible list

#### Scenario: Ambiguous release requires candidate selection
- **WHEN** the add-payload API responds with an error containing a list of candidate assets
- **THEN** the form displays a candidate picker instead of submitting, and the user must select a candidate before resubmitting

#### Scenario: Category suggestions while adding
- **WHEN** a user types into the category field on the add-mirror form
- **THEN** the field offers the distinct set of non-empty categories currently present across the loaded mirror list as suggestions, without restricting submission to one of them

### Requirement: Edit Mirror
The frontend SHALL allow editing an existing mirror's source URL, description, category, and selected asset via a modal dialog, including re-resolving ambiguous releases. The category input SHALL suggest categories already in use across the current mirror list as the user types.

#### Scenario: Opening the edit dialog
- **WHEN** a user clicks the edit action on a mirror row
- **THEN** a modal dialog opens pre-filled with the mirror's current URL, description, and category, and shows the currently selected asset name

#### Scenario: Changing the selected file
- **WHEN** a user clicks "Change file…" in the edit dialog
- **THEN** the app fetches the candidate assets for that mirror's source and displays a candidate picker, pre-selecting the candidate matching the current asset if still available

#### Scenario: Saving edits
- **WHEN** a user submits the edit dialog with valid data
- **THEN** the edit-payload API is called and, on success, the dialog closes and the row reflects the updated payload

#### Scenario: Closing without saving
- **WHEN** a user clicks the backdrop, the close button, or Cancel in the edit dialog
- **THEN** the dialog closes and no changes are persisted

#### Scenario: Category suggestions while editing
- **WHEN** a user types into the category field in the edit-mirror dialog
- **THEN** the field offers the distinct set of non-empty categories currently present across the loaded mirror list as suggestions, without restricting submission to one of them
