# mirror-editing Specification

## Purpose

TBD - created by archiving change add-mirror-editing. Update Purpose after
archive.

## Requirements

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

#### Scenario: Source URL change preserves manual sort order and hidden status
- **WHEN** a user edits an existing mirror's source URL, causing its fields
  to be rebuilt and replaced
- **THEN** the system SHALL carry over that mirror's existing `sort_order`
  and hidden status onto the rebuilt record, unchanged
- **AND** the system SHALL NOT reset the mirror's position in the manually
  chosen ordering or change whether it is hidden, purely as a side effect of
  the source URL edit

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

### Requirement: Edit an existing mirror's title without re-resolving the source
The system SHALL allow updating a mirror's `title` without contacting any
external release/source when the source URL is unchanged, the same way
`description`-only edits are handled today. Changing `title` MAY still
change the mirror's `name`/`filename` locally (see "Renaming a mirror when
its title changes"), but SHALL NOT itself trigger any network request to
the mirror's source.

#### Scenario: Title-only edit is a local patch
- **WHEN** a user edits only the `title` of an existing mirror
- **THEN** the system SHALL update the stored `title` (and, if the derived
  slug differs from the current `name`, the `name`/`filename`) for that item
  in place, and SHALL NOT perform any network request to the mirror's source

#### Scenario: Title edit combined with an asset/file switch
- **WHEN** a user edits an existing mirror's `title` at the same time as
  switching its `asset_name` and/or `extract_file` (source URL unchanged)
- **THEN** the system SHALL persist the new `title` (and any resulting
  `name`/`filename` change) alongside the re-resolved asset data, without
  the title edit itself triggering any extra network request beyond what
  the asset switch already requires

### Requirement: Set a mirror's title when adding it
The system SHALL allow specifying an optional `title` when adding a new
mirror. When a `title` is given, the mirror's `name` SHALL be derived from
it (see "Deriving a mirror's name from its title") instead of from the
source repo name; when no `title` is given, `name` is derived from the
source repo exactly as it is today.

#### Scenario: Add with an explicit title
- **WHEN** a user adds a new mirror and supplies a `title`
- **THEN** the system SHALL store that `title` on the new mirror record and
  SHALL derive the mirror's `name` (and thus `filename`) from the title
  instead of from the source repo name

#### Scenario: Add without a title
- **WHEN** a user adds a new mirror without supplying a `title`
- **THEN** the system SHALL create the mirror with no stored `title` and a
  `name` derived from the source repo, exactly as before this change

### Requirement: Deriving a mirror's name from its title
The system SHALL derive a mirror's `name` from a non-empty `title` by
lowercasing it, replacing every run of characters outside `[a-z0-9]` with a
single `-`, and stripping any leading/trailing `-`.

#### Scenario: Title slugifies to a name
- **WHEN** a mirror's `title` is `"PS5 Bar Tool - All"`
- **THEN** the system SHALL derive `name` as `"ps5-bar-tool-all"`

### Requirement: Renaming a mirror when its title changes
The system SHALL keep an existing mirror's `name` and `filename` in sync
with its `title`: when an edit changes `title` such that its derived slug
differs from the mirror's current `name`, the system SHALL rename the
mirror's on-disk file and update its stored `name`/`filename`/`url` at its
current list position, without re-downloading the asset.

#### Scenario: Changing the title renames the entry
- **WHEN** a user edits an existing mirror and changes its `title` to a
  value whose derived slug differs from the mirror's current `name`
- **THEN** the system SHALL rename the mirror's file on disk to match the
  newly derived `filename`, and SHALL update the stored `name`, `filename`,
  and `url` for that item, in place at its current list position

#### Scenario: Title change that slugifies to the same name is a no-op rename
- **WHEN** a user edits an existing mirror's `title` to a new value whose
  derived slug equals the mirror's current `name`
- **THEN** the system SHALL update the stored `title` without renaming any
  file or changing `name`/`filename`

#### Scenario: Renaming preserves sort order, hidden status, and description
- **WHEN** a title change causes a mirror to be renamed
- **THEN** the system SHALL carry over that mirror's `sort_order`, hidden
  status, and `description` unchanged, exactly as an asset/file switch does
  today

### Requirement: Title-driven rename rejects a colliding name
The system SHALL reject a title change whose derived slug matches a
*different* existing mirror's `name`, leaving both mirrors' records and
files untouched.

#### Scenario: New title's slug collides with another mirror
- **WHEN** a user edits a mirror's `title` to a value whose derived slug
  equals another, different mirror's current `name`
- **THEN** the system SHALL reject the edit with an error, and SHALL NOT
  modify either mirror's stored record or on-disk file

#### Scenario: New title's slug collides only with the mirror's own current name
- **WHEN** a user edits a mirror's `title` to a value whose derived slug
  equals that same mirror's own current `name`
- **THEN** the system SHALL NOT reject the edit on collision grounds (this
  is the no-op rename case, not a collision)
