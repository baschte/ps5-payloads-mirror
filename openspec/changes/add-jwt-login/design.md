## Context

See `proposal.md` — Why. The constraints that shape the approach:

- **Deployment topology**: an nginx-proxy-manager container terminates TLS and
  forwards to the app over the **host IP and published port** (`docker-compose.yml`
  publishes `${PORT:-8000}:8000`). The app therefore only ever sees plain HTTP,
  and the published port stays reachable directly from the LAN. Both access
  paths must keep working.
- **Single credential pair**: there is exactly one user, configured via
  `MIRROR_AUTH_USER` / `MIRROR_AUTH_PASSWORD`. No user store, no registration,
  no roles.
- **Existing structure**: authentication today is a single `@app.middleware("http")`
  in `server/main.py` with a two-entry public path allowlist. The frontend is a
  React 18 SPA with no router — navigation is conditional rendering only.
- **Public consumers**: `/payloads.json` is consumed by third parties and
  `/api/health` by the container healthcheck. Neither may ever require a session.

## Goals / Non-Goals

**Goals:**

- Fail-closed protection of the management API: a newly added endpoint is
  protected unless someone deliberately places it on the allowlist.
- A login flow that works identically through the HTTPS proxy and over direct
  plain-HTTP LAN access, without configuration changes.
- No new required environment variable — an existing `.env` keeps working as-is.
- Session state that survives container restarts, so routine rebuilds do not
  sign the user out.

**Non-Goals:**

- Multi-user accounts, roles, password reset, or a user store.
- Server-side session revocation lists. With one user, changing the password is
  the revocation mechanism.
- Refresh-token rotation or a separate refresh endpoint. A single sliding
  session cookie is sufficient at this scale.
- Absolute session lifetime caps on top of the idle timeout.
- Protecting the frontend bundle. It is public by design after this change.

## Decisions

### D1: Keep a middleware, not per-route dependencies

The guard stays an HTTP middleware rather than moving to `Depends(...)` on each
route.

- *Why*: fail-closed. There are ~20 management endpoints and more will be added;
  a middleware protects them by construction, whereas a forgotten `Depends` is a
  silent hole. The middleware is also the natural place to re-issue the sliding
  cookie, since it already holds the response object.
- *Alternative considered*: a `Depends(require_session)` on a shared router.
  Cleaner OpenAPI output and easier to test per-route, but it makes "protected"
  opt-in. Rejected on safety grounds.

### D2: Protect by path prefix — everything under `/api/` except an allowlist

```
/api/health          → public   (container healthcheck)
/api/auth/login      → public   (obviously)
/api/auth/logout     → public   (must work with an expired session)
/api/auth/me         → public route, reports 401 when unauthenticated
/api/*               → PROTECTED
/payloads.json       → public   (not under /api/, third-party consumers)
/, /assets/*, /*     → public   (SPA shell — the login screen must render)
```

- *Why*: one rule, and it lines up with the "everything the browser needs to
  boot is public, everything that mutates state is not" boundary.
- *Note*: this is the **breaking** part of the change — the frontend bundle
  becomes world-readable. It contains no secrets; the risk is disclosure of the
  app's existence and shape, which the login screen reveals anyway.

### D3: Signing secret derived from the configured credentials

```
secret = pbkdf2_hmac("sha256",
                     password = f"{MIRROR_AUTH_USER}\0{MIRROR_AUTH_PASSWORD}",
                     salt     = b"ps5-payloads-mirror/jwt-session/v1",
                     iterations = 200_000)
```

Computed once at import time (~100 ms, paid at startup only).

- *Why*: no new environment variable; deterministic, so sessions survive
  restarts; a username or password change rotates the secret and invalidates
  every outstanding token — which is exactly the desired behavior.
- *Alternatives considered*: a random secret generated per process (signs the
  user out on every rebuild — this deployment restarts often), or a required
  `MIRROR_JWT_SECRET` (another value to configure, and one more thing to lose).
- The fixed salt is domain separation, not password hardening — the input is
  already a high-entropy-by-assumption secret held in the same `.env`.

### D4: PyJWT with a pinned algorithm

`jwt.encode(..., algorithm="HS256")` and `jwt.decode(..., algorithms=["HS256"])`.

- Passing `algorithms` explicitly is mandatory — it is what prevents `alg: none`
  and RS/HS confusion attacks. Never decode with `verify=False`.
- Claims: `sub` (username), `iat`, `exp`. Nothing else; the token is not a place
  to cache application state.
- *Alternative considered*: hand-rolled HS256 over `hmac`/`hashlib` (~40 lines,
  no new dependency). Rejected in favour of a maintained library that gets the
  edge cases right. Cost: `pyproject.toml` + `Dockerfile` change and an image
  rebuild.

### D5: Sliding session, re-issued lazily

Idle lifetime **8 hours**. The middleware re-issues the cookie only when more
than **half** the lifetime has elapsed since `iat`.

- *Why the halfway rule*: re-issuing on every request would put a `Set-Cookie`
  on every JSON response, including the scheduler's polling traffic. The
  halfway rule bounds the write rate while guaranteeing an actively used session
  never expires.

### D6: `Secure` flag resolved per request, overridable

`MIRROR_COOKIE_SECURE` ∈ `auto` (default) | `true` | `false`.

`auto` marks the cookie `Secure` when the effective request scheme is HTTPS. For
that to be true behind the proxy, uvicorn must trust the forwarded headers:

```yaml
# docker-compose.yml
environment:
  FORWARDED_ALLOW_IPS: "*"
```

Uvicorn defaults this to `127.0.0.1`; the proxy arrives from another address, so
without this the forwarded scheme is ignored and the cookie silently loses
`Secure`.

- *Why `*` is acceptable here*: the only forwarded header this app consults is
  the scheme, and the only thing it influences is the `Secure` flag on the
  caller's **own** cookie. A LAN client that spoofs `X-Forwarded-Proto: https`
  over plain HTTP merely breaks its own login. No cross-user impact, no
  authorization decision depends on client IP (see D7).
- *Alternative considered*: hardcoding `Secure=true` and closing the published
  port. Cleaner, but it removes the LAN access path the deployment relies on.

### D7: Throttling by global exponential delay, not per-IP lockout

```
attempt fails  → failures += 1
delay          = min(0.5s * 2^(failures-1), 5s)      # applied BEFORE verifying
attempt succeeds → failures = 0
```

- *Why not per-IP*: every request through the proxy carries the same source
  address, so per-IP counting is meaningless for proxied traffic — and using
  `X-Forwarded-For` instead is worthless when the port is also directly
  reachable and the header is trivially spoofed.
- *Why delay instead of lockout*: a shared counter with hard lockout would let
  anyone lock the legitimate user out. A delay caps brute-force throughput at
  ~0.2 attempts/second while a correct password always eventually succeeds.
- The handler is `async def` and uses `asyncio.sleep`, so the delay parks the
  coroutine instead of occupying a threadpool worker.

### D8: 401 without `WWW-Authenticate`

Unauthenticated requests get a plain JSON 401. Emitting `WWW-Authenticate` would
make the browser open its native Basic Auth dialog on top of the React login
screen — the exact behavior being removed.

### D9: Frontend — context + module-level 401 hook

```
main.tsx
└── <AuthProvider>                 status: 'loading'|'anon'|'authed'|'disabled'
    └── <AuthGate>
        ├── status 'loading'   → neutral splash (no flash of login form)
        ├── status 'anon'      → <LoginScreen>
        └── 'authed'|'disabled'→ <App>   ← mounts only when access is permitted
```

- `api.ts` cannot import React state. It exposes a registration function
  (`setUnauthorizedHandler`) that `AuthProvider` wires up once; the central
  `request()` helper calls it on any 401 and throws a marker error the callers
  skip toasting. Avoids a circular import and keeps every existing call site
  unchanged.
- Mounting `<App>` only when access is permitted means the existing data-loading
  effects, and the scheduler's polling interval in `SchedulerPanel`, start and
  stop with the session for free — no per-call guards needed.
- The bootstrap effect calling `/api/auth/me` must be idempotent under React 18
  StrictMode double-invocation.

## Risks / Trade-offs

- **Frontend bundle becomes public** → Unavoidable for a self-rendered login
  screen. Mitigated by the bundle containing no secrets and the API staying
  closed. Called out as BREAKING in the proposal.
- **`FORWARDED_ALLOW_IPS: "*"` is broad** → Scoped by D6: the app reads only the
  scheme and applies it only to the caller's own cookie. If the published port
  is ever closed off, this can be tightened to the proxy's address.
- **Password lives in `.env` in cleartext, and now also derives the signing
  secret** → Unchanged exposure in practice: anyone who can read `.env` already
  had full access. Accepted deliberately (no hash support in this change).
- **A password change silently signs everyone out** → Intended, but surprising
  during a routine credential rotation. Documented in `README.md`.
- **`auto` cookie security is per-origin** → `https://mirror.tld` and
  `http://host:8000` are different origins with independent cookies, so signing
  in on one does not sign in on the other. Documented rather than fixed.
- **Session state lives only in the token** → No server-side revocation short of
  a password change. Accepted for a single-user deployment (Non-Goals).
- **The throttle is process-global** → A determined attacker can make the
  legitimate login slow (max 5 s), though never impossible. Accepted as strictly
  better than a lockout.

## Migration Plan

1. Deploy requires a **rebuild**, not just a restart — PyJWT is a new image
   dependency (`docker compose up -d --build`).
2. Add `FORWARDED_ALLOW_IPS` to `docker-compose.yml`. `MIRROR_COOKIE_SECURE` is
   optional; leaving it unset yields `auto`.
3. Existing `.env` files need no edit. Deployments with both auth variables set
   get the login screen; deployments with them empty stay fully open.
4. First load after deploy: browsers that cached Basic Auth credentials will
   simply see the login screen. Users may need to clear a stale Basic Auth
   session for the origin if the browser keeps re-sending the header (harmless —
   it is ignored).
5. **Rollback**: revert the commit and rebuild. No persisted data or on-disk
   format changes, so rollback is unconditional and safe at any time.
