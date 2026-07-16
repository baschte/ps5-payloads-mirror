## MODIFIED Requirements

### Requirement: Add a mirror
The system SHALL allow adding a new mirror by resolving a release source URL,
downloading the selected asset, and persisting the derived metadata,
optionally paired with a caller-supplied `title`.

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

#### Scenario: Add request includes a title
- **WHEN** a client submits a new mirror with a non-empty `title`
- **THEN** the system SHALL persist that `title` on the created mirror
  record, derive its `name` from the title (rather than the source repo
  name), and return the created record in the response

#### Scenario: Add request's title slug collides with an existing mirror
- **WHEN** a client submits a new mirror with a `title` whose derived slug
  matches an existing mirror's `name`
- **THEN** the system SHALL reject the request without creating a new
  mirror, the same way a duplicate source is rejected

### Requirement: Edit a mirror renames it when its title changes
The system SHALL allow updating a mirror's `title` via the edit endpoint,
and SHALL keep `name`/`filename` derived from `title` when one is set,
renaming the mirror's stored record and on-disk file as needed.

#### Scenario: Edit request changes the title
- **WHEN** a client edits an existing mirror with a `title` whose derived
  slug differs from the mirror's current `name`
- **THEN** the system SHALL rename the mirror (updating `name`, `filename`,
  `url`, and `title`) and return the updated record, addressable at its new
  `name` for subsequent requests

#### Scenario: Edit request's new title slug collides with a different mirror
- **WHEN** a client edits an existing mirror with a `title` whose derived
  slug matches a *different* mirror's current `name`
- **THEN** the system SHALL reject the request without modifying either
  mirror's stored record or on-disk file
