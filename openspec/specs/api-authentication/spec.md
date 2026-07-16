# api-authentication Specification

## Purpose
TBD - created by archiving change api-baseline. Update Purpose after archive.
## Requirements
### Requirement: Optional HTTP Basic Auth
The system SHALL support gating all endpoints except a fixed public allowlist
behind HTTP Basic Auth, activated only when both a username and password are
configured.

#### Scenario: Auth disabled when not configured
- **WHEN** no username/password is configured for the deployment
- **THEN** the system SHALL allow every request through without requiring
  credentials

#### Scenario: Auth enabled when fully configured
- **WHEN** both a username and password are configured for the deployment
- **THEN** the system SHALL require valid Basic Auth credentials on every
  request except the public allowlist

### Requirement: Public allowlist stays open when auth is enabled
The system SHALL always allow unauthenticated access to the raw payloads
feed and the health check, even when Basic Auth is otherwise enabled.

#### Scenario: Public feed bypasses auth
- **WHEN** Basic Auth is enabled and a client requests the raw payloads feed
  without credentials
- **THEN** the system SHALL serve the feed without requiring authentication

#### Scenario: Health check bypasses auth
- **WHEN** Basic Auth is enabled and a client requests the health check
  without credentials
- **THEN** the system SHALL serve the health check without requiring
  authentication

### Requirement: Invalid or missing credentials are rejected
The system SHALL reject requests to protected endpoints that lack valid
credentials when Basic Auth is enabled, without revealing which part of the
credential was wrong.

#### Scenario: Missing credentials
- **WHEN** Basic Auth is enabled and a client requests a protected endpoint
  with no `Authorization` header
- **THEN** the system SHALL respond with an unauthorized status and a
  `WWW-Authenticate` challenge, and SHALL NOT process the request

#### Scenario: Incorrect credentials
- **WHEN** Basic Auth is enabled and a client supplies a username or
  password that does not match the configured credentials
- **THEN** the system SHALL respond with an unauthorized status and SHALL
  NOT process the request

#### Scenario: Credential comparison does not leak timing information
- **WHEN** the system compares supplied credentials against the configured
  ones
- **THEN** the system SHALL use a constant-time comparison so that
  response timing does not reveal how much of the credential matched

