## ADDED Requirements

### Requirement: Mirrors have a persisted, explicit sort order
The system SHALL track an explicit `sort_order` value per mirror and SHALL
use it as the sole ordering key for stored data and API responses, instead
of ordering by last-update recency.

#### Scenario: New mirror is appended to the end
- **WHEN** a new mirror is added
- **THEN** the system SHALL assign it a `sort_order` greater than every
  other existing mirror's `sort_order`, placing it last

#### Scenario: Order is stable across unrelated saves
- **WHEN** any mirror is added, edited, updated, or refreshed by a scheduled
  run
- **THEN** the system SHALL NOT change the relative order of mirrors whose
  `sort_order` was not explicitly modified by that operation

### Requirement: Users can persist a manual reorder of all mirrors
The system SHALL provide a way to submit a complete new ordering of all
known mirrors and SHALL persist it as each mirror's new `sort_order`.

#### Scenario: Reordering the full set
- **WHEN** a user submits a new ordering containing every currently known
  mirror name, each exactly once, in the desired order
- **THEN** the system SHALL assign each mirror a `sort_order` consistent
  with that order and persist it in a single write

#### Scenario: Submitted ordering doesn't match the known set
- **WHEN** a reorder request's set of names does not exactly match the
  system's current set of known mirror names (missing, extra, or duplicate
  names)
- **THEN** the system SHALL reject the request with an error and SHALL NOT
  change any mirror's `sort_order`

### Requirement: Reordering works across visible and hidden mirrors together
The system SHALL allow a reorder operation to include both visible and
hidden mirrors in a single ordering, since both are presented together in
the UI.

#### Scenario: Reordering a mix of visible and hidden mirrors
- **WHEN** a user's submitted ordering includes both visible and hidden
  mirrors interleaved
- **THEN** the system SHALL persist the resulting `sort_order` values
  consistently for both visible and hidden mirrors, regardless of which
  underlying storage location each mirror's record lives in
