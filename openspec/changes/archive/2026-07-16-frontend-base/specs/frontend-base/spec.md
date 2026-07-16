## ADDED Requirements

### Requirement: App Shell and Theming
The frontend SHALL render a single-page app shell with a header (logo, collection title, action buttons) and a main content area, and SHALL support a persisted light/dark theme toggle applied before first paint.

#### Scenario: Theme persists across reloads
- **WHEN** a user toggles the theme and reloads the page
- **THEN** the previously selected theme is read from `localStorage` and applied to the document before the app renders, avoiding a flash of the wrong theme

#### Scenario: Theme toggle updates document state
- **WHEN** a user clicks the theme toggle button
- **THEN** the `.dark` class on the document root is added or removed, the choice is persisted to `localStorage`, and the `theme-color` meta tag is updated to match

### Requirement: Collection Title Editing
The frontend SHALL allow the collection title to be viewed and edited inline in the header.

#### Scenario: Editing and saving the title
- **WHEN** a user clicks the pencil icon next to the title, changes the text, and presses Enter (or clicks the check button)
- **THEN** the app calls the update-title API, shows a success toast on completion, and refreshes git-publish status since the title is part of tracked content

#### Scenario: Cancelling a title edit
- **WHEN** a user is editing the title and presses Escape (or clicks the cancel button)
- **THEN** the edit is discarded and the previously saved title is shown unchanged

### Requirement: Mirror List Loading and Display
The frontend SHALL fetch the list of mirrored payloads on load and render them in a table, showing a loading state while the initial fetch is in flight and an empty state when there are none.

#### Scenario: Initial load
- **WHEN** the app mounts
- **THEN** it fetches the payload list and the collection title, showing a loading placeholder until the payload list request resolves

#### Scenario: Empty mirror list
- **WHEN** the fetched payload list is empty
- **THEN** the table area renders an empty-state message instead of a table

#### Scenario: Load failure
- **WHEN** the initial payload list fetch fails
- **THEN** an error toast is shown with the failure message (or a generic fallback if the error has no message)

### Requirement: Add Mirror
The frontend SHALL provide a form to add a new mirror from a release URL, with an optional description, and SHALL support resolving ambiguous releases by letting the user pick a candidate asset.

#### Scenario: Successful add
- **WHEN** a user submits a valid release URL (and optional description)
- **THEN** the app calls the add-payload API, and on success clears the form and adds the new payload to the visible list

#### Scenario: Ambiguous release requires candidate selection
- **WHEN** the add-payload API responds with an error containing a list of candidate assets
- **THEN** the form displays a candidate picker instead of submitting, and the user must select a candidate before resubmitting

### Requirement: Update Individual Mirror
The frontend SHALL allow updating a single mirror to fetch its latest release.

#### Scenario: Update in progress
- **WHEN** a user clicks the update action on a mirror row
- **THEN** that row shows a busy/updating state (disabling its other actions) until the update-payload API responds, after which the row reflects the new payload data and a result toast is shown

### Requirement: Update All Mirrors
The frontend SHALL allow updating every mirror in one action.

#### Scenario: Update all in progress
- **WHEN** a user clicks "Update all"
- **THEN** the update-all API is called, the button is disabled while in flight, and on completion the payload list is refreshed and a summary toast is shown

### Requirement: Edit Mirror
The frontend SHALL allow editing an existing mirror's source URL, description, and selected asset via a modal dialog, including re-resolving ambiguous releases.

#### Scenario: Opening the edit dialog
- **WHEN** a user clicks the edit action on a mirror row
- **THEN** a modal dialog opens pre-filled with the mirror's current URL and description, and shows the currently selected asset name

#### Scenario: Changing the selected file
- **WHEN** a user clicks "Change file…" in the edit dialog
- **THEN** the app fetches the candidate assets for that mirror's source and displays a candidate picker, pre-selecting the candidate matching the current asset if still available

#### Scenario: Saving edits
- **WHEN** a user submits the edit dialog with valid data
- **THEN** the edit-payload API is called and, on success, the dialog closes and the row reflects the updated payload

#### Scenario: Closing without saving
- **WHEN** a user clicks the backdrop, the close button, or Cancel in the edit dialog
- **THEN** the dialog closes and no changes are persisted

### Requirement: Remove Mirror
The frontend SHALL allow removing a mirror after explicit confirmation.

#### Scenario: Confirmed removal
- **WHEN** a user clicks the remove action on a mirror row and confirms the native confirmation prompt
- **THEN** the delete-payload API is called and, on success, the mirror is removed from the visible list

#### Scenario: Cancelled removal
- **WHEN** a user clicks the remove action but declines the confirmation prompt
- **THEN** no API call is made and the mirror remains in the list

### Requirement: Hide/Show Mirror
The frontend SHALL allow toggling a mirror's visibility without deleting it, and SHALL visually distinguish hidden mirrors.

#### Scenario: Hiding a mirror
- **WHEN** a user clicks the hide action on a visible mirror
- **THEN** the set-hidden API is called with `hidden: true`, the row is updated to show a "Hidden" indicator and reduced opacity, and a toast confirms the change

#### Scenario: Showing a hidden mirror
- **WHEN** a user clicks the show action on a hidden mirror
- **THEN** the set-hidden API is called with `hidden: false`, the row returns to full opacity without the "Hidden" indicator, and a toast confirms the change

### Requirement: Manual Reordering
The frontend SHALL allow reordering mirrors via drag-and-drop, applying the change optimistically and reverting on failure.

#### Scenario: Successful reorder
- **WHEN** a user drags a mirror row and drops it onto another row's position
- **THEN** the local list order updates immediately, the reorder API is called with the full new name order, and the optimistic order is kept once the API confirms success

#### Scenario: Failed reorder
- **WHEN** the reorder API call fails after an optimistic reorder
- **THEN** the list reverts to its pre-drag order and an error toast is shown

### Requirement: Update Scheduler Panel
The frontend SHALL provide a panel to view and configure automatic update scheduling, and to trigger an immediate run, independent of the mirror list.

#### Scenario: Viewing scheduler status
- **WHEN** the scheduler panel is visible
- **THEN** it polls the scheduler status endpoint on an interval (more frequently while a run is in progress) and displays whether scheduling is enabled, the last run result, and the next scheduled run time

#### Scenario: Editing schedule without losing in-progress edits
- **WHEN** a status poll resolves while the user has unsaved changes to the enabled toggle or interval
- **THEN** the unsaved form values are preserved and only the read-only status fields are updated

#### Scenario: Saving schedule changes
- **WHEN** a user changes the enabled toggle or interval and clicks Save
- **THEN** the update-scheduler API is called with the new configuration, and the Save button becomes disabled (showing a saved state) once the values match the server-confirmed configuration

#### Scenario: Triggering an immediate run
- **WHEN** a user clicks "Run now"
- **THEN** the run-now API is called, the button is disabled while the run is in progress or already running, and completion of the run (detected via a changed last-run timestamp) triggers a toast and a refresh of the mirror list

### Requirement: Git Publish Status and Actions
The frontend SHALL surface whether git-publish is configured and whether there are pending changes to publish, and SHALL allow triggering a publish action.

#### Scenario: Publish button visibility
- **WHEN** git-publish is not enabled on the backend
- **THEN** the publish button is not rendered

#### Scenario: Publish button availability
- **WHEN** git-publish is enabled but there are no pending changes
- **THEN** the publish button is rendered but disabled, with a tooltip indicating there is nothing to publish

#### Scenario: Triggering a publish
- **WHEN** git-publish is enabled with pending changes and the user clicks Publish
- **THEN** the git-push API is called, the button shows a publishing state while in flight, and on completion a toast reports whether changes were pushed or only committed

### Requirement: Toast Notifications
The frontend SHALL surface the result of asynchronous actions via a single transient, auto-dismissing toast notification.

#### Scenario: Toast auto-dismiss timing
- **WHEN** a toast is shown
- **THEN** it automatically dismisses after 4 seconds for success/info messages or 7 seconds for error messages, unless manually dismissed sooner

#### Scenario: Manual dismissal
- **WHEN** a user clicks the toast's close button
- **THEN** the toast is dismissed immediately

### Requirement: API Error Handling with Candidate Recovery
The frontend SHALL treat HTTP error responses uniformly, extracting a human-readable message and, when present, a list of candidate assets for ambiguous-release recovery flows.

#### Scenario: Generic API error
- **WHEN** any API call returns a non-2xx response without candidate data
- **THEN** the error is surfaced as a message-only error usable directly in a toast

#### Scenario: Ambiguous-release API error
- **WHEN** an API call returns a 422 response with a structured `{message, candidates}` error body
- **THEN** the error exposes the candidate list so the calling form can render a candidate picker instead of only showing an error message
