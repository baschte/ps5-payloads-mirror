## ADDED Requirements

### Requirement: Git publish is opt-in via configuration
The system SHALL only enable git publishing (status and manual/auto push)
when git credentials and author identity are fully configured, git is
available, and the working directory is a git repository.

#### Scenario: Publishing disabled when not configured
- **WHEN** git username, password, author name, or author email is missing,
  git is unavailable, or the working directory is not a git repository
- **THEN** the system SHALL report git publishing as disabled and SHALL
  reject any manual publish attempt with an error explaining what is
  missing

### Requirement: Report pending publish status
The system SHALL report whether there are uncommitted changes to the tracked
mirror data files waiting to be published.

#### Scenario: Pending changes detected
- **WHEN** a client requests git status while publishing is enabled and the
  tracked data files (`payloads.json`, `README.md`) have uncommitted changes
- **THEN** the system SHALL report publishing as enabled and pending as true

#### Scenario: No pending changes
- **WHEN** a client requests git status while publishing is enabled and the
  tracked data files have no uncommitted changes
- **THEN** the system SHALL report pending as false

### Requirement: Hidden mirrors are never published
The system SHALL exclude hidden-mirror storage from every commit and push,
so hidden mirrors remain local-only.

#### Scenario: Hidden mirror data is not staged
- **WHEN** a git publish (manual or automatic) runs
- **THEN** the system SHALL stage and commit only `payloads.json` and
  `README.md`, and SHALL NOT stage, commit, or push the hidden-mirrors file

### Requirement: Manual publish commits and pushes pending changes
The system SHALL allow triggering a commit and push of the tracked data
files on demand, rebasing onto the remote before pushing and never
force-pushing.

#### Scenario: Successful manual publish
- **WHEN** a client triggers a manual publish while there are uncommitted
  changes to the tracked data files
- **THEN** the system SHALL commit those changes, rebase onto the remote's
  latest commit (auto-resolving in favor of the local commit on conflicting
  hunks in the tracked files), push the result, and report success

#### Scenario: Nothing to publish
- **WHEN** a client triggers a manual publish while there are no
  uncommitted changes to the tracked data files
- **THEN** the system SHALL report that nothing was committed or pushed,
  without creating an empty commit

#### Scenario: Publish never force-pushes
- **WHEN** the rebase onto the remote's latest commit cannot be
  auto-resolved
- **THEN** the system SHALL abort the rebase, leave the local commit
  intact, and report an error, and SHALL NOT force-push

#### Scenario: Credentials never leak in error output
- **WHEN** a git command invoked during publish fails and its output is
  returned to the client
- **THEN** the system SHALL scrub the configured password from that output
  before returning it

### Requirement: Auto-publish debounces and coalesces changes
The system SHALL automatically publish pending changes a configurable delay
after the most recent mirror data write, coalescing multiple writes within
the delay window into a single publish, when auto-publish is enabled and
publishing is configured.

#### Scenario: Single publish after a burst of changes
- **WHEN** several mirror data writes happen in quick succession, each
  within the configured delay window of the previous one
- **THEN** the system SHALL perform exactly one publish after the delay
  following the last write, not one per write

#### Scenario: Auto-publish disabled
- **WHEN** auto-publish is disabled via configuration, or git publishing
  itself is not configured
- **THEN** the system SHALL NOT automatically publish on data writes,
  leaving changes to be published manually

#### Scenario: New changes during an in-flight publish get their own round
- **WHEN** a mirror data write occurs while a previously-triggered
  auto-publish is still running
- **THEN** the system SHALL re-arm the debounce timer so the new change is
  published in a subsequent round after the current publish finishes

### Requirement: Report auto-publish status
The system SHALL report whether auto-publish is enabled, its configured
delay, whether a publish is currently running, whether one is pending, and
the result of the last publish attempt.

#### Scenario: Status reflects current auto-publish state
- **WHEN** a client requests auto-publish status
- **THEN** the system SHALL return whether it is enabled, its delay in
  seconds, whether a publish is currently in progress, whether one is
  pending (debounce timer armed), and the last result message if any
