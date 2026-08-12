# api-authentication Specification

## Purpose
TBD - created by archiving change api-baseline. Update Purpose after archive.
## Requirements
### Requirement: Optional session-based authentication
The system SHALL support gating the management API behind a login-based
session, activated only when both a username and password are configured for
the deployment. When authentication is disabled the system SHALL behave as if
every request is authenticated.

#### Scenario: Auth disabled when not configured
- **WHEN** no username/password is configured for the deployment
- **THEN** the system SHALL allow every request through without requiring a
  session, and SHALL report to the frontend that authentication is disabled

#### Scenario: Auth enabled when fully configured
- **WHEN** both a username and password are configured for the deployment
- **THEN** the system SHALL require a valid session on every management API
  request except the public allowlist

#### Scenario: Partial configuration does not enable auth
- **WHEN** only one of username or password is configured
- **THEN** the system SHALL treat authentication as disabled rather than
  locking the deployment out with credentials that cannot be satisfied

### Requirement: Login establishes a session
The system SHALL expose a login endpoint that accepts a username and password
and, on success, establishes an authenticated session carried by a cookie that
client-side scripts cannot read.

#### Scenario: Successful login
- **WHEN** a client posts the configured username and password to the login
  endpoint
- **THEN** the system SHALL respond with a success status and set a session
  cookie marked `HttpOnly`, `SameSite=Lax`, and scoped to the whole site

#### Scenario: Rejected login
- **WHEN** a client posts a username or password that does not match the
  configured credentials
- **THEN** the system SHALL respond with an unauthorized status, SHALL NOT set
  a session cookie, and SHALL return a single generic message that does not
  reveal which of the two values was wrong

#### Scenario: Credential comparison does not leak timing information
- **WHEN** the system compares supplied credentials against the configured ones
- **THEN** the system SHALL use a constant-time comparison so that response
  timing does not reveal how much of the credential matched

#### Scenario: Login while authentication is disabled
- **WHEN** authentication is disabled and a client posts to the login endpoint
- **THEN** the system SHALL respond with a success status without setting a
  session cookie, so a client that attempts to log in is never stuck

### Requirement: Session tokens are signed and expiring
The system SHALL carry sessions as tokens signed with a secret that is not
stored in configuration, and SHALL reject any token that is unsigned, altered,
expired, or signed with a different secret.

#### Scenario: Tampered token is rejected
- **WHEN** a request presents a session token whose payload or signature has
  been modified
- **THEN** the system SHALL reject the request as unauthenticated

#### Scenario: Expired token is rejected
- **WHEN** a request presents a session token whose expiry time has passed
- **THEN** the system SHALL reject the request as unauthenticated

#### Scenario: Password change invalidates existing sessions
- **WHEN** the configured password is changed and the system is restarted
- **THEN** session tokens issued before the change SHALL no longer be accepted

#### Scenario: Sessions survive a restart
- **WHEN** the system is restarted without any configuration change
- **THEN** session tokens issued before the restart SHALL still be accepted
  until they expire

### Requirement: Sessions extend while in use
The system SHALL renew a session's lifetime on authenticated activity, so that
a continuously used session does not expire mid-work, while an idle session
does expire.

#### Scenario: Active session is extended
- **WHEN** an authenticated request is served with a valid, unexpired session
- **THEN** the system SHALL issue a refreshed session cookie with a new expiry

#### Scenario: Idle session expires
- **WHEN** no authenticated request is made for longer than the session
  lifetime
- **THEN** the next request SHALL be rejected as unauthenticated

### Requirement: Session cookie security depends on the request scheme
The system SHALL mark the session cookie `Secure` when the request reached it
over HTTPS, and SHALL support overriding that decision by configuration so the
deployment works both behind an HTTPS reverse proxy and over plain HTTP on a
local network.

#### Scenario: Request arrives over HTTPS through a proxy
- **WHEN** a login request reaches the system through a trusted reverse proxy
  that reports the original scheme as HTTPS
- **THEN** the session cookie SHALL be marked `Secure`

#### Scenario: Request arrives over plain HTTP
- **WHEN** a login request reaches the system directly over plain HTTP
- **THEN** the session cookie SHALL NOT be marked `Secure`, so that the login
  still works on a local network

#### Scenario: Explicit override
- **WHEN** the deployment configures the cookie security explicitly as enabled
  or disabled
- **THEN** the system SHALL use that value regardless of the request scheme

### Requirement: Logout ends the session
The system SHALL expose a logout endpoint that invalidates the caller's session
cookie.

#### Scenario: Logging out
- **WHEN** an authenticated client posts to the logout endpoint
- **THEN** the system SHALL clear the session cookie, and subsequent requests
  without a new login SHALL be rejected as unauthenticated

#### Scenario: Logging out without a session
- **WHEN** an unauthenticated client posts to the logout endpoint
- **THEN** the system SHALL respond successfully rather than with an error

### Requirement: Session status is queryable
The system SHALL expose an endpoint that reports whether authentication is
enabled for the deployment and whether the caller currently holds a valid
session, so a client can decide what to render before making any other call.

#### Scenario: Query with a valid session
- **WHEN** a client with a valid session queries the session status endpoint
- **THEN** the system SHALL report that the caller is authenticated and include
  the signed-in username

#### Scenario: Query without a session
- **WHEN** a client without a valid session queries the session status endpoint
- **THEN** the system SHALL respond with an unauthorized status rather than an
  error that a client cannot distinguish from a server fault

#### Scenario: Query while authentication is disabled
- **WHEN** authentication is disabled and a client queries the session status
  endpoint
- **THEN** the system SHALL report success and indicate that authentication is
  disabled

### Requirement: Login attempts are throttled
The system SHALL slow down repeated failed login attempts so that credentials
cannot be brute-forced, and SHALL do so without any client being able to lock
another client out.

#### Scenario: Repeated failures are progressively delayed
- **WHEN** consecutive login attempts fail
- **THEN** each subsequent attempt SHALL be delayed by a progressively longer
  interval, up to a fixed maximum

#### Scenario: Successful login clears the penalty
- **WHEN** a login succeeds after one or more failures
- **THEN** the delay SHALL reset so the next attempt is served without penalty

#### Scenario: Throttling cannot deny service
- **WHEN** the throttle is at its maximum delay
- **THEN** a request presenting correct credentials SHALL still succeed after
  that delay, and SHALL never be rejected outright

### Requirement: Public allowlist stays open when auth is enabled
The system SHALL always allow unauthenticated access to the raw payloads feed,
the health check, the authentication endpoints themselves, and the static
frontend assets, even when authentication is otherwise enabled. Serving the
frontend shell publicly is required so the login screen can be rendered before
any credentials exist.

#### Scenario: Public feed bypasses auth
- **WHEN** authentication is enabled and a client requests the raw payloads
  feed without a session
- **THEN** the system SHALL serve the feed without requiring authentication

#### Scenario: Health check bypasses auth
- **WHEN** authentication is enabled and a client requests the health check
  without a session
- **THEN** the system SHALL serve the health check without requiring
  authentication

#### Scenario: Frontend shell bypasses auth
- **WHEN** authentication is enabled and a client requests the frontend
  document or one of its static assets without a session
- **THEN** the system SHALL serve them so the login screen can render

#### Scenario: Management endpoints stay protected
- **WHEN** authentication is enabled and a client requests any management API
  endpoint outside the allowlist without a valid session
- **THEN** the system SHALL reject the request as unauthenticated and SHALL NOT
  process it
