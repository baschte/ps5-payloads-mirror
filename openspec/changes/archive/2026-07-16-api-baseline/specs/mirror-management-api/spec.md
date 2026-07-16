## ADDED Requirements

### Requirement: List all mirrors
The system SHALL expose a read endpoint that returns every stored mirror,
including hidden ones, with all persisted fields.

#### Scenario: Listing returns full stored data
- **WHEN** a client requests the list of mirrors
- **THEN** the system SHALL return every mirror currently persisted
  (visible and hidden), including any extra fields stored on the item

### Requirement: Public raw payloads feed
The system SHALL serve the exact on-disk `payloads.json` file at a stable,
unauthenticated URL, open to cross-origin requests, so external consumers can
read the mirror feed without going through the management API.

#### Scenario: Public feed is reachable without credentials
- **WHEN** a client requests the raw payloads feed, with or without
  credentials, while authentication is enabled
- **THEN** the system SHALL return the current `payloads.json` file contents
  with `Access-Control-Allow-Origin: *`

#### Scenario: Public feed reflects the same data as the management API
- **WHEN** the stored mirror data changes
- **THEN** subsequent requests to the raw payloads feed SHALL reflect the
  updated data, matching what `list mirrors` returns for visible mirrors

### Requirement: Add a mirror
The system SHALL allow adding a new mirror by resolving a release source URL,
downloading the selected asset, and persisting the derived metadata.

#### Scenario: Successful add
- **WHEN** a client submits a new mirror with a valid, not-yet-mirrored
  source URL
- **THEN** the system SHALL resolve the latest release, download the
  selected asset, persist a new mirror record, and return it

#### Scenario: Duplicate source is rejected
- **WHEN** a client submits a source URL that resolves to a source already
  mirrored by an existing item
- **THEN** the system SHALL reject the request without creating a new
  mirror or modifying the existing one

#### Scenario: Ambiguous release requires a candidate choice
- **WHEN** a client submits a source URL whose latest release has more than
  one plausible asset or extractable file, without specifying which to use
- **THEN** the system SHALL reject the request with the list of candidate
  choices, and SHALL NOT persist a new mirror

### Requirement: Update a single mirror
The system SHALL allow re-checking a single mirror against its source and
persisting any new release data.

#### Scenario: Update finds a newer release
- **WHEN** a client requests an update for an existing mirror whose source
  has a newer release than the one currently stored
- **THEN** the system SHALL download the new asset, update the mirror's
  stored metadata, and report that it was updated

#### Scenario: Update finds no change
- **WHEN** a client requests an update for an existing mirror whose source
  has no newer release
- **THEN** the system SHALL leave the mirror's stored metadata unchanged and
  report that it was not updated

#### Scenario: Update for an unknown mirror
- **WHEN** a client requests an update for a mirror name that does not exist
- **THEN** the system SHALL reject the request without persisting any
  change

### Requirement: Update all mirrors
The system SHALL allow triggering an update check across every stored
mirror in one request, continuing past individual failures.

#### Scenario: Bulk update reports per-item results
- **WHEN** a client requests an update of all mirrors
- **THEN** the system SHALL attempt to update every stored mirror and
  return a per-mirror result indicating whether each was updated

#### Scenario: One mirror's failure does not block others
- **WHEN** a client requests an update of all mirrors and one mirror's
  source is unreachable or invalid
- **THEN** the system SHALL still attempt and report results for the
  remaining mirrors

### Requirement: Remove a mirror
The system SHALL allow permanently deleting a mirror by name.

#### Scenario: Successful removal
- **WHEN** a client deletes an existing mirror by name
- **THEN** the system SHALL remove it from the stored data so it no longer
  appears in subsequent listings or the public feed

#### Scenario: Removing an unknown mirror
- **WHEN** a client attempts to delete a mirror name that does not exist
- **THEN** the system SHALL reject the request without modifying the
  stored data

### Requirement: Concurrent writes are serialized
The system SHALL serialize all mutating operations on the stored mirror data
(add, edit, update-one, update-all, remove, reorder, hide) so that no two
writes race against each other.

#### Scenario: Overlapping mutations do not corrupt data
- **WHEN** two mutating requests against the mirror data arrive at
  approximately the same time
- **THEN** the system SHALL apply them one at a time, and the stored data
  SHALL reflect both changes with no lost update

### Requirement: Health check
The system SHALL expose an unauthenticated health check that reports service
status and the current mirror count.

#### Scenario: Health check succeeds without credentials
- **WHEN** a client requests the health check, with or without credentials,
  while authentication is enabled
- **THEN** the system SHALL respond with an ok status and the number of
  currently stored mirrors
