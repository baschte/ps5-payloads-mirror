## ADDED Requirements

### Requirement: Authentication Gate
The frontend SHALL determine the session state before rendering the app shell
and SHALL render a login screen in place of the app whenever authentication is
enabled and no valid session exists. While the session state is still unknown,
the frontend SHALL render neither the login screen nor the app, so a signed-in
user never sees the login form flash on load.

#### Scenario: Signed-out user sees the login screen
- **WHEN** the app mounts, authentication is enabled, and no valid session
  exists
- **THEN** the login screen is rendered instead of the app shell, and no
  management API calls are made

#### Scenario: Signed-in user sees the app
- **WHEN** the app mounts and a valid session exists
- **THEN** the app shell is rendered and the normal initial data loading
  proceeds

#### Scenario: No login screen when auth is disabled
- **WHEN** the backend reports that authentication is not configured
- **THEN** the app shell is rendered directly and no login screen or sign-out
  control is shown

#### Scenario: No flash of the login form
- **WHEN** the app is mounting and the session state has not resolved yet
- **THEN** a neutral loading state is rendered, and neither the login screen nor
  the app shell appears until the session state is known

#### Scenario: Session check fails
- **WHEN** the session status request fails for a reason other than being
  unauthenticated, such as the backend being unreachable
- **THEN** the login screen is shown with an explanatory message rather than an
  indefinite loading state

### Requirement: Login Form
The frontend SHALL provide a login form that submits a username and password,
communicates progress and failure inline, and hands control to the app shell on
success.

#### Scenario: Successful sign-in
- **WHEN** a user submits valid credentials
- **THEN** the form shows a busy state while the request is in flight and, on
  success, the app shell replaces the login screen and loads its data

#### Scenario: Failed sign-in
- **WHEN** a user submits credentials the backend rejects
- **THEN** an error message is shown inline on the form, the password field is
  cleared and refocused, and the login screen remains

#### Scenario: Submitting an incomplete form
- **WHEN** a user submits the form with an empty username or password
- **THEN** no request is made and the browser surfaces the missing required
  field

#### Scenario: Form is usable with assistive technology and password managers
- **WHEN** the login screen is rendered
- **THEN** the fields are a labelled username and password pair inside a form
  element with the autocomplete hints password managers expect, the username
  field receives focus on mount, and error messages are announced

### Requirement: Sign Out
The frontend SHALL provide a sign-out control in the app shell whenever
authentication is enabled, which ends the session and returns to the login
screen.

#### Scenario: Signing out
- **WHEN** a signed-in user activates the sign-out control
- **THEN** the logout request is sent and the login screen replaces the app
  shell

#### Scenario: Sign-out failure still signs out locally
- **WHEN** the logout request fails
- **THEN** the frontend still discards its local session state and returns to
  the login screen rather than leaving the user in an ambiguous state

### Requirement: Expired Session Handling
The frontend SHALL treat an unauthorized response from any management API call
as an expired session, returning to the login screen instead of surfacing it as
an ordinary error.

#### Scenario: Session expires during use
- **WHEN** any management API call responds as unauthorized
- **THEN** the frontend clears its session state and renders the login screen,
  without showing a generic error toast for that call

#### Scenario: Background polling does not spam errors
- **WHEN** a periodic background request, such as scheduler status polling,
  responds as unauthorized
- **THEN** the frontend returns to the login screen and stops the polling
  rather than repeatedly reporting failures

#### Scenario: Signing back in restores the app
- **WHEN** a user signs in again after their session expired
- **THEN** the app shell is rendered and its data is loaded fresh

## MODIFIED Requirements

### Requirement: Mirror List Loading and Display
The frontend SHALL fetch the list of mirrored payloads once the session state is
known and access is permitted, and render them in a table, showing a loading
state while the initial fetch is in flight and an empty state when there are
none. The table's `Payload`, `Version`, `Updated`, and `Source` headers SHALL
act as sort controls, as specified by the `mirror-table-sorting` capability.
Each row SHALL display the mirror's category, when it has one, as specified by
the `payload-categories` capability.

#### Scenario: Initial load
- **WHEN** the app shell mounts with a resolved session that permits access
- **THEN** it fetches the payload list and the collection title, showing a
  loading placeholder until the payload list request resolves

#### Scenario: No data is fetched while signed out
- **WHEN** authentication is enabled and no valid session exists
- **THEN** the payload list and collection title are not requested

#### Scenario: Empty mirror list
- **WHEN** the fetched payload list is empty
- **THEN** the table area renders an empty-state message instead of a table

#### Scenario: Load failure
- **WHEN** the initial payload list fetch fails
- **THEN** an error toast is shown with the failure message (or a generic
  fallback if the error has no message)

#### Scenario: Rows are rendered in the active order
- **WHEN** the payload list is rendered
- **THEN** rows appear in the active sort order if a sort is active, and
  otherwise in the order returned by the backend
