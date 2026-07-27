## ADDED Requirements

### Requirement: A mirror has at most one free-text category
The system SHALL store at most one category per mirror, as a free-text string with no fixed or enforced vocabulary, and SHALL treat an absent or empty category as "no category" rather than persisting an empty string.

#### Scenario: Setting a category
- **WHEN** a user sets a non-empty category on a mirror, whether at add time or via edit
- **THEN** the system SHALL persist that exact string (trimmed of leading/trailing whitespace) as the mirror's category

#### Scenario: Leaving the category blank
- **WHEN** a user adds or edits a mirror without entering a category
- **THEN** the system SHALL store no category for that mirror, distinct from any specific category value

#### Scenario: Clearing a previously set category
- **WHEN** a user edits a mirror that currently has a category and empties the category field before saving
- **THEN** the system SHALL remove the stored category from that mirror

#### Scenario: A category is never a list
- **WHEN** a mirror's category is set
- **THEN** the system SHALL represent it as a single string value, never as multiple values or an array, matching the one-category-per-mirror rule

### Requirement: Category is set and edited without re-resolving the source
The system SHALL allow setting or changing a mirror's category, at add time or via edit, without that change alone triggering any network request to the mirror's upstream source.

#### Scenario: Category-only edit is a local patch
- **WHEN** a user edits only the category of an existing mirror, leaving its source URL unchanged
- **THEN** the system SHALL update the stored category in place and SHALL NOT perform any network request to the mirror's source

#### Scenario: Category is independent of asset/file selection
- **WHEN** a user changes a mirror's selected asset or extracted file via edit
- **THEN** the system SHALL leave that mirror's stored category unchanged unless the category field is also explicitly changed in the same edit

### Requirement: Category is included in mirror listings and the public feed
The system SHALL include each mirror's category (when set) among the fields returned by the mirror list endpoint and the public payloads feed, so downstream consumers can group mirrors by category.

#### Scenario: A categorized mirror appears with its category
- **WHEN** a mirror with a stored category is included in a list-mirrors response or the public feed
- **THEN** that mirror's entry SHALL include its category value

#### Scenario: An uncategorized mirror omits the field
- **WHEN** a mirror with no stored category is included in a list-mirrors response or the public feed
- **THEN** that mirror's entry SHALL NOT claim any specific category value

### Requirement: Category input offers suggestions from categories already in use
The frontend SHALL suggest previously used categories as the user types into the category field, on both the add-mirror form and the edit-mirror dialog, without restricting the field to only those suggestions.

#### Scenario: Suggestions reflect current usage
- **WHEN** a user focuses or types into a category field
- **THEN** the frontend SHALL offer, as suggestions, the distinct set of non-empty categories currently present across the loaded mirror list

#### Scenario: A new category can still be entered
- **WHEN** a user types a category value that does not match any suggestion
- **THEN** the frontend SHALL accept it as a valid new category on submit, without requiring it to match an existing suggestion

#### Scenario: Suggestions update as mirrors change
- **WHEN** a mirror is added, edited, or removed such that the set of categories in use changes
- **THEN** subsequently opened category inputs SHALL reflect the updated set of suggestions

### Requirement: A mirror's category is visible in the mirror table
The frontend SHALL display a mirror's category, when it has one, in the mirror table without requiring the edit dialog to be opened.

#### Scenario: A categorized mirror shows its category
- **WHEN** a mirror with a stored category is rendered in the mirror table
- **THEN** its row SHALL display that category as a visible label

#### Scenario: An uncategorized mirror shows no category label
- **WHEN** a mirror with no stored category is rendered in the mirror table
- **THEN** its row SHALL NOT display any category label
