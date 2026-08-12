## Why

The UI is currently gated by HTTP Basic Auth, which means the browser's native
credential dialog — no branding, no logout, no session, and no way to show a
friendly error. It also gates the static frontend bundle, so the app cannot
render anything of its own before credentials are accepted. Replacing it with a
native login screen backed by a signed session token gives a real sign-in
experience, an explicit sign-out, and room for future hardening (rate limiting,
session expiry) that Basic Auth cannot express.

## What Changes

- **BREAKING**: HTTP Basic Auth is removed entirely. Clients that today send an
  `Authorization: Basic …` header (scripts, bookmarks with embedded
  credentials) will no longer be authenticated and must use the login endpoint.
- **BREAKING**: The static frontend (`index.html`, `/assets/*`) becomes publicly
  readable so the login screen can render before authentication. Only `/api/*`
  stays protected. The bundle contains no secrets, but this is a visible change
  from today's "nothing is reachable without credentials".
- New session endpoints: `POST /api/auth/login`, `POST /api/auth/logout`,
  `GET /api/auth/me`.
- The session is carried by an `HttpOnly`, `SameSite=Lax` cookie holding a
  short-lived HS256 JWT, renewed on each authenticated request (sliding
  session).
- The signing secret is derived from `MIRROR_AUTH_PASSWORD` via HKDF — no new
  required environment variable, stable across container restarts, and a
  password change invalidates every existing session.
- New optional environment variable `MIRROR_COOKIE_SECURE` (`auto` | `true` |
  `false`, default `auto`) so the deployment works both behind the HTTPS reverse
  proxy and via direct LAN access on plain HTTP.
- Login attempts are throttled by a global exponential delay rather than per-IP
  blocking, because every proxied request shares a single source address.
- The frontend gains an auth context, a login screen rendered in place of the
  app shell while signed out, a sign-out control, and a central 401 interceptor
  that returns to the login screen instead of emitting error toasts.
- `MIRROR_AUTH_USER` / `MIRROR_AUTH_PASSWORD` keep their names and meaning:
  both empty still means "no authentication at all".

## Capabilities

### New Capabilities

None. The existing `api-authentication` capability already owns this behavior;
its requirements are being replaced rather than supplemented.

### Modified Capabilities

- `api-authentication`: the Basic Auth requirements are replaced by
  session-token requirements — login/logout/session endpoints, cookie
  attributes and their HTTPS behavior, token derivation and expiry, the
  enlarged public allowlist (static assets alongside the payloads feed and
  health check), and login throttling.
- `frontend-base`: the app shell gains an authentication gate — the login
  screen shown while unauthenticated, session bootstrap on mount without a
  flash of the login form, sign-out, and uniform handling of expired sessions
  across every API call.

## Impact

- **Code**: `server/main.py` (auth middleware replaced by dependency + new
  routes), new `server/auth.py`; `web/src/api.ts` (401 interceptor),
  `web/src/App.tsx` (gate), new `web/src/auth/` module and login components.
- **Dependencies**: adds `PyJWT` to `pyproject.toml` and the Docker image — a
  rebuild is required, an image pull alone is not enough.
- **Configuration**: `.env.example` and `docker-compose.yml` gain
  `MIRROR_COOKIE_SECURE` and `FORWARDED_ALLOW_IPS`.
- **Docs**: `README.md` and `WEBUI.md` describe Basic Auth today and must be
  rewritten for the login flow.
- **Operations**: `/payloads.json` and `/api/health` stay public, so external
  consumers of the mirror list and the container healthcheck are unaffected.
  Everyone currently signed in via the browser's Basic Auth store will be
  presented with the new login screen once deployed.
