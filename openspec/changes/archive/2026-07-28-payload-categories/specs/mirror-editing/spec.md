## MODIFIED Requirements

### Requirement: Edit an existing mirror's metadata without re-resolving the source
The system SHALL allow updating a mirror's `description` and/or `category`
without contacting any external release/source when the source URL is
unchanged.

#### Scenario: Description-only edit is a local patch
- **WHEN** a user edits only the `description` of an existing mirror
- **THEN** the system SHALL update the stored `description` for that item in
  place and SHALL NOT perform any network request to the mirror's source

#### Scenario: Category-only edit is a local patch
- **WHEN** a user edits only the `category` of an existing mirror
- **THEN** the system SHALL update the stored `category` for that item in
  place and SHALL NOT perform any network request to the mirror's source

#### Scenario: Clearing the category is a local patch
- **WHEN** a user edits an existing mirror to remove its `category`, leaving
  every other field unchanged
- **THEN** the system SHALL remove the stored `category` for that item in
  place and SHALL NOT perform any network request to the mirror's source
