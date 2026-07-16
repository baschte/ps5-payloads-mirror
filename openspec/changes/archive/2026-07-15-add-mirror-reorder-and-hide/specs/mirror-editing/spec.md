## MODIFIED Requirements

### Requirement: Edit an existing mirror's source URL
The system SHALL allow changing a mirror's source URL, re-resolving the
release and selected asset the same way a new mirror is added.

#### Scenario: Source URL change re-resolves and replaces in place
- **WHEN** a user edits an existing mirror and supplies a new source URL
- **THEN** the system SHALL resolve the new URL's repo, fetch its latest
  release, determine the candidate asset/file exactly as it would for adding
  a new mirror
- **AND** the system SHALL overwrite the existing mirror's fields (name,
  filename, url, source, source_direct, version, checksum, asset_pattern,
  extract_file) at its current position in the payload list, rather than
  appending a new entry

#### Scenario: Editing to a URL that changes the derived name
- **WHEN** a user edits an existing mirror's source URL to a different
  repository, causing the derived mirror name to change
- **THEN** the system SHALL still replace the item at its original list
  position with the newly resolved data, using the new name

#### Scenario: Source URL change preserves manual sort order and hidden status
- **WHEN** a user edits an existing mirror's source URL, causing its fields
  to be rebuilt and replaced
- **THEN** the system SHALL carry over that mirror's existing `sort_order`
  and hidden status onto the rebuilt record, unchanged
- **AND** the system SHALL NOT reset the mirror's position in the manually
  chosen ordering or change whether it is hidden, purely as a side effect of
  the source URL edit
