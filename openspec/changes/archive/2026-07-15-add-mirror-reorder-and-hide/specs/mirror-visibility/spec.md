## ADDED Requirements

### Requirement: A mirror can be hidden without deleting it
The system SHALL allow marking an existing mirror as hidden, removing its
record from the published, git-tracked mirror file while preserving all of
its data so it can be reactivated later.

#### Scenario: Hiding a mirror
- **WHEN** a user hides an existing mirror
- **THEN** the system SHALL move that mirror's complete record out of the
  git-tracked mirror data file into a separate, non-git-tracked storage
  location, without discarding any of its fields

#### Scenario: Hidden mirror is excluded from published output
- **WHEN** a mirror is hidden
- **THEN** the system SHALL exclude it from the public payloads feed and
  from the generated README table

### Requirement: A hidden mirror can be reactivated
The system SHALL allow reactivating a previously hidden mirror, restoring
its record to the published, git-tracked mirror data file.

#### Scenario: Reactivating a hidden mirror
- **WHEN** a user reactivates a previously hidden mirror
- **THEN** the system SHALL move that mirror's complete record back into the
  git-tracked mirror data file
- **AND** the mirror SHALL again appear in the public payloads feed and the
  generated README table

### Requirement: Hidden storage is never committed or published
The system SHALL ensure the storage location used for hidden mirrors is
never included in version control commits or in any publish/push operation.

#### Scenario: Publishing does not include hidden mirror data
- **WHEN** a publish (commit and push) operation runs
- **THEN** the system SHALL NOT stage, commit, or push the hidden-mirrors
  storage location, regardless of its contents

### Requirement: Hidden mirrors continue to receive automatic updates
The system SHALL continue to check hidden mirrors for upstream updates and
refresh their files, versions, and checksums during scheduled and manual
"update all" operations, exactly as it does for visible mirrors.

#### Scenario: Scheduled update touches a hidden mirror
- **WHEN** a scheduled or manually triggered "update all" operation runs
  while a mirror is hidden
- **THEN** the system SHALL check that mirror for an upstream update and
  apply it under the same conditions as it would for a visible mirror

### Requirement: The management API exposes visible and hidden mirrors together
The system SHALL return both visible and hidden mirrors from the
authenticated mirror-listing API, each tagged with its hidden status, in a
single ordered list.

#### Scenario: Listing mirrors includes hidden ones
- **WHEN** a user requests the full list of mirrors via the management API
- **THEN** the system SHALL include both visible and hidden mirrors in the
  response, each indicating whether it is hidden
