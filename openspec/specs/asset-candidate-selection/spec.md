# asset-candidate-selection Specification

## Purpose

TBD - created by archiving change add-mirror-editing. Update Purpose after
archive.

## Requirements

### Requirement: Unified candidate list across top-level assets and ZIP members
When resolving a release for add or edit, the system SHALL build a single
flattened list of plausible candidates consisting of every plausible
top-level release asset, plus (for any top-level asset that is a ZIP) every
plausible `.elf`/`.bin` member inside that ZIP.

#### Scenario: Release with multiple top-level assets
- **WHEN** a release has more than one plausible top-level asset (e.g. two
  `.elf` files, or an `.elf` and a `.zip`)
- **THEN** the system SHALL include every plausible top-level asset as a
  distinct candidate in the resolution result

#### Scenario: ZIP asset contributes its members as candidates
- **WHEN** a plausible top-level asset is a `.zip` file
- **THEN** the system SHALL inspect its contents and include each plausible
  `.elf`/`.bin` member inside it as a distinct candidate, associated with
  that parent asset

### Requirement: Single unambiguous candidate is auto-selected
The system SHALL NOT prompt the user when exactly one plausible candidate
exists for a release.

#### Scenario: Exactly one plausible candidate
- **WHEN** resolving a release for add or edit yields exactly one plausible
  candidate (whether a single top-level asset or the sole member of a single
  ZIP asset)
- **THEN** the system SHALL select that candidate automatically without
  requiring user input

### Requirement: Ambiguous candidates always require explicit user choice
The system SHALL require an explicit user choice whenever more than one
plausible candidate exists, for both add and edit, instead of silently
picking one via heuristic.

#### Scenario: Multiple candidates require a choice
- **WHEN** resolving a release for add or edit yields more than one
  plausible candidate
- **THEN** the system SHALL reject the request with an ambiguity error that
  includes the full flattened candidate list
- **AND** the system SHALL accept a follow-up request that specifies exactly
  one of the listed candidates and proceed using that selection

#### Scenario: Candidate choice applies identically to add and edit
- **WHEN** an ambiguous release is encountered during either an add
  operation or an edit operation
- **THEN** the system SHALL apply the same candidate-listing and
  explicit-choice behavior in both cases

### Requirement: Automatic updates resolve deterministically from a stored candidate
Unattended update operations (scheduled updates, "update all", and a single
update triggered without an interactive choice) SHALL resolve the asset to
use by filtering strictly against the mirror's previously stored candidate,
without prompting and without re-applying a scoring heuristic.

#### Scenario: Stored candidate still present in a newer release
- **WHEN** an automatic update checks a mirror whose stored candidate
  (top-level asset identity, and member name if applicable) still exists in
  the latest release
- **THEN** the system SHALL select that exact candidate deterministically
  without scoring or prompting

#### Scenario: Stored candidate no longer present
- **WHEN** an automatic update checks a mirror whose stored candidate can no
  longer be found in the latest release (renamed or removed asset/member)
- **THEN** the system SHALL fail that mirror's update with an error message,
  reported through the existing update-result/notification path, and SHALL
  NOT fall back to guessing a different candidate

#### Scenario: Existing mirror with no previously recorded candidate
- **WHEN** an automatic update checks a mirror created before this
  capability existed and has no usable stored candidate
- **THEN** the system SHALL select an asset using the prior scoring
  heuristic exactly once, and SHALL persist that selection as the mirror's
  stored candidate so subsequent updates resolve deterministically
