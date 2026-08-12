## 1. Dependency and configuration

- [x] 1.1 Add `PyJWT>=2.8.0` to `dependencies` in `pyproject.toml`
- [x] 1.2 Add the same pin to the `pip install` layer in `Dockerfile` (kept in sync with `pyproject.toml`, as the existing comment states)
- [x] 1.3 Add `MIRROR_COOKIE_SECURE` and `FORWARDED_ALLOW_IPS: "*"` to the `environment:` block in `docker-compose.yml`, with comments explaining why the forwarded headers must be trusted (design D6)
- [x] 1.4 Document `MIRROR_COOKIE_SECURE` in `.env.example` and update the `MIRROR_AUTH_USER` / `MIRROR_AUTH_PASSWORD` comment block to describe the login screen instead of Basic Auth

## 2. Backend: session module (`server/auth.py`)

- [x] 2.1 Create `server/auth.py` reading `MIRROR_AUTH_USER`, `MIRROR_AUTH_PASSWORD`, `MIRROR_COOKIE_SECURE`; expose `AUTH_ENABLED` (both credentials non-empty — partial configuration means disabled)
- [x] 2.2 Derive the signing secret once at import via `hashlib.pbkdf2_hmac` over `user\0password` with the fixed salt and 200_000 iterations (design D3); skip derivation entirely when auth is disabled
- [x] 2.3 Implement `issue_token(username)` and `decode_token(raw)` using PyJWT HS256 with `algorithms=["HS256"]` passed explicitly on decode, claims `sub`/`iat`/`exp`, 8-hour lifetime (design D4, D5)
- [x] 2.4 Implement `verify_credentials(user, password)` using `secrets.compare_digest` on both values so comparison stays constant-time
- [x] 2.5 Implement `cookie_secure(request)` resolving `auto` from the effective request scheme, and `true`/`false` as explicit overrides (design D6)
- [x] 2.6 Implement `set_session_cookie(response, token, request)` and `clear_session_cookie(response)` with `HttpOnly`, `SameSite=Lax`, `Path=/`, and `Max-Age` matching the token lifetime
- [x] 2.7 Implement the login throttle: module-level failure counter guarded by an `asyncio.Lock`, `min(0.5 * 2**(n-1), 5.0)` seconds awaited before verification, reset on success (design D7)

## 3. Backend: middleware and routes (`server/main.py`)

- [x] 3.1 Remove the Basic Auth block entirely — `AUTH_USER`/`AUTH_PASSWORD`/`AUTH_ENABLED`, `_credentials_ok`, the `basic_auth` middleware, and the now-unused `base64` import
- [x] 3.2 Add the session middleware: allow anything not under `/api/`, allow `/api/health` and `/api/auth/*`, require a valid session for everything else, returning JSON 401 **without** a `WWW-Authenticate` header (design D2, D8)
- [x] 3.3 In the same middleware, re-issue the session cookie on successful authenticated requests once more than half the token lifetime has elapsed (design D5)
- [x] 3.4 Add `POST /api/auth/login` (async) — throttle, verify, issue token, set cookie; return a single generic message on failure; return success without a cookie when auth is disabled
- [x] 3.5 Add `POST /api/auth/logout` — clear the cookie, always succeed even without a session
- [x] 3.6 Add `GET /api/auth/me` — `{authenticated, auth_enabled, username}` on success, 401 when auth is enabled and no valid session exists
- [x] 3.7 Verify `/payloads.json` (with its CORS header) and `/api/health` still respond without a session, and that the SPA fallback plus `/assets/*` serve unauthenticated

## 4. Frontend: session plumbing

- [x] 4.1 Add auth types to `web/src/types.ts` (session status shape) and an `UnauthorizedError` marker error
- [x] 4.2 In `web/src/api.ts`, add `setUnauthorizedHandler()` and invoke it from the central `request()` helper on any 401, throwing the marker error (design D9)
- [x] 4.3 Add `login`, `logout`, and `getSession` API functions alongside the existing ones
- [x] 4.4 Create `web/src/auth/AuthProvider.tsx` with a context holding `'loading' | 'anon' | 'authed' | 'disabled'`, bootstrapping via `getSession()` on mount (idempotent under StrictMode) and registering the 401 handler
- [x] 4.5 Create `web/src/auth/useAuth.ts` exposing the context with a descriptive error when used outside the provider
- [x] 4.6 Handle a failed session check (network/server error, not 401) by landing on the login screen with an explanatory message rather than an endless splash

## 5. Frontend: login UI and gate

- [x] 5.1 Create `web/src/components/LoginScreen.tsx` — a real `<form>` with labelled username/password inputs, `autoComplete="username"` / `"current-password"`, autofocus on the username field, inline error with an accessible live region, busy state while submitting, and password cleared + refocused on failure
- [x] 5.2 Style the login screen with the existing Tailwind tokens so it matches the app's light/dark theme, and ensure the theme is applied on the login screen too
- [x] 5.3 Create the gate in `web/src/main.tsx`: wrap in `AuthProvider` and render splash / `LoginScreen` / `App` by status, so `App` mounts only when access is permitted
- [x] 5.4 Add a sign-out control to the header in `web/src/App.tsx`, rendered only when auth is enabled, clearing local session state even if the logout request fails
- [x] 5.5 Ensure no toast is shown for requests that failed with the 401 marker error — the return to the login screen is the feedback

## 6. Documentation

- [x] 6.1 Rewrite the auth section of `README.md`: login screen instead of Basic Auth, `MIRROR_COOKIE_SECURE`, the rebuild requirement, and that changing the password signs everyone out
- [x] 6.2 Update `WEBUI.md` with the login flow, the public-path list, and the note that the frontend bundle is now public

## 7. Verification

- [x] 7.1 Run `npm run build` in `web/` — TypeScript must compile clean
- [x] 7.2 With auth configured, verify via `start.sh`: login screen appears, wrong credentials show an inline error and get progressively slower, correct credentials load the app, sign-out returns to the login screen
- [x] 7.3 Verify the session cookie carries `HttpOnly`, `SameSite=Lax`, and no `Secure` over plain HTTP; confirm `document.cookie` cannot read it
- [x] 7.4 Verify unauthenticated `curl` against `/api/payloads` returns 401 with no `WWW-Authenticate`, while `/payloads.json` and `/api/health` return 200
- [x] 7.5 Verify that with both auth variables empty the app loads with no login screen and no sign-out control
- [x] 7.6 Run `openspec validate add-jwt-login --strict`
