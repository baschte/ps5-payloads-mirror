## ADDED Requirements

### Requirement: Edit an existing mirror's metadata without re-resolving the source
The system SHALL allow updating a mirror's `description` without contacting
any external release/source when the source URL is unchanged.

#### Scenario: Description-only edit is a local patch
- **WHEN** a user edits only the `description` of an existing mirror
- **THEN** the system SHALL update the stored `description` for that item in
  place and SHALL NOT perform any network request to the mirror's source

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

### Requirement: Duplicate-source check excludes the item being edited
The system SHALL NOT reject an edit as a duplicate source merely because the
edited item's own (soon-to-be-replaced) source matches.

#### Scenario: Editing a mirror back to its own current source
- **WHEN** a user edits a mirror and supplies a source URL that is the same
  as (or resolves to the same source as) that mirror's current source
- **THEN** the system SHALL NOT raise a duplicate-source error for that
  item's own existing record

#### Scenario: Editing a mirror to another mirror's existing source
- **WHEN** a user edits a mirror and supplies a source URL matching a
  *different* existing mirror's source
- **THEN** the system SHALL raise a duplicate-source error, unchanged from
  today's add-time behavior

### Requirement: Switch a mirror's chosen asset/file without changing its source URL
The system SHALL allow changing which asset or ZIP member a mirror tracks
while its source URL stays unchanged, and SHALL provide a read-only way to
list the current source's candidates on demand so this choice can be made
before submitting an edit.

#### Scenario: Asset switch with an unchanged source URL
- **WHEN** a user edits an existing mirror and supplies a different
  `asset_name` (and/or `extract_file`) while leaving the source URL the same
- **THEN** the system SHALL re-fetch that source's latest release, resolve
  the newly specified candidate, and re-download/re-extract it as needed
- **AND** the system SHALL NOT change the mirror's `source` field

#### Scenario: Switching away from a ZIP-derived asset clears the stale member selection
- **WHEN** a user switches a mirror from a ZIP-derived asset to a non-ZIP
  asset (with the source URL unchanged)
- **THEN** the system SHALL clear the mirror's previously stored
  `extract_file`, since it no longer applies to the newly selected asset

#### Scenario: Listing candidates for the current source without editing
- **WHEN** a user requests the candidate list for an existing mirror's
  current (unchanged) source
- **THEN** the system SHALL re-fetch that source's latest release and return
  its full flattened candidate list without persisting any change to the
  mirror

### Requirement: Edit failures surface through existing error handling
The system SHALL report edit failures (unresolvable URL, no suitable asset,
duplicate source, ambiguous candidates) through the same error path used by
add and update operations today, without introducing a new persisted status
field.

#### Scenario: Edit fails to resolve a new source
- **WHEN** a user edits a mirror's source URL to a URL that cannot be
  resolved to a repo/release, or has no suitable asset
- **THEN** the system SHALL reject the edit with an error message describing
  the failure and SHALL leave the existing mirror record unchanged
