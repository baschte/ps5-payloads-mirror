## ADDED Requirements

### Requirement: Read scheduler status
The system SHALL expose the scheduler's current configuration and run state:
whether it is enabled, its interval, whether an update is currently running,
and the last/next run times with a summary of the last run.

#### Scenario: Status reflects current configuration and state
- **WHEN** a client requests scheduler status
- **THEN** the system SHALL return whether it is enabled, the configured
  interval in hours, whether an update is currently in progress, the last
  run time and summary (if any), and the next scheduled run time when
  enabled

#### Scenario: Next run is absent when disabled
- **WHEN** a client requests scheduler status while the scheduler is
  disabled
- **THEN** the system SHALL report no next run time

### Requirement: Configure scheduler enablement and interval
The system SHALL allow enabling/disabling the scheduler and setting its
update interval, clamped to between 1 and 24 hours, persisting the
configuration so it survives a restart.

#### Scenario: Enabling and setting a valid interval
- **WHEN** a client sets the scheduler to enabled with an interval within
  1-24 hours
- **THEN** the system SHALL persist the new configuration, recompute the
  next run time from now, and apply the new interval to future waits
  immediately rather than waiting out the previous interval

#### Scenario: Interval is clamped to the allowed range
- **WHEN** a client requests an interval outside 1-24 hours
- **THEN** the system SHALL clamp the stored interval to the nearest bound
  within 1-24 hours rather than rejecting the request

#### Scenario: Disabling the scheduler
- **WHEN** a client sets the scheduler to disabled
- **THEN** the system SHALL stop scheduling future automatic runs until
  re-enabled, without affecting any update already in progress

### Requirement: Trigger an immediate update
The system SHALL allow triggering an update run immediately, independent of
the configured interval, without starting a second concurrent run.

#### Scenario: Run-now while idle
- **WHEN** a client triggers an immediate update while no update is
  currently running
- **THEN** the system SHALL start an update run in the background and
  return the current status

#### Scenario: Run-now while already running
- **WHEN** a client triggers an immediate update while one is already in
  progress
- **THEN** the system SHALL NOT start a second concurrent update, and
  SHALL return the current (already-running) status

### Requirement: Scheduled updates never overlap manual mutations
The system SHALL ensure a scheduled or manually-triggered update run shares
the same data lock as manual mirror mutations, so it can never read or write
mirror data concurrently with an add/edit/remove/reorder/hide request.

#### Scenario: Scheduled update waits for an in-flight manual edit
- **WHEN** a scheduled update's due time arrives while a manual mutation
  (add/edit/remove/reorder/hide) is in progress
- **THEN** the system SHALL wait for the manual mutation to finish before
  starting the update, rather than running concurrently

### Requirement: A single failing mirror does not crash the scheduler
The system SHALL keep the scheduler loop running even if an update run
raises an unexpected error, recording the failure in the run summary.

#### Scenario: Update run fails
- **WHEN** a scheduled or manually-triggered update run raises an
  unexpected error
- **THEN** the system SHALL record a failure summary and last-run time,
  mark the run as no longer in progress, and continue scheduling future
  runs normally
