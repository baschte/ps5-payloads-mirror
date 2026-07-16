# collection-title Specification

## Purpose
TBD - created by archiving change api-baseline. Update Purpose after archive.
## Requirements
### Requirement: Read the collection title
The system SHALL expose the current display title of the mirror collection.

#### Scenario: Reading the title
- **WHEN** a client requests the collection title
- **THEN** the system SHALL return the currently stored title

### Requirement: Update the collection title
The system SHALL allow setting the collection's display title to a new
non-empty value, persisting it immediately.

#### Scenario: Successful title update
- **WHEN** a client submits a new title between 1 and 120 characters
- **THEN** the system SHALL persist the new title and return it as the
  current title

#### Scenario: Rejecting an invalid title
- **WHEN** a client submits an empty title or one longer than 120
  characters
- **THEN** the system SHALL reject the request and SHALL NOT change the
  stored title

