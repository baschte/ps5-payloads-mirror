"""Session authentication for the management API.

The UI is gated by a native login screen rather than HTTP Basic Auth. A
successful login issues a short-lived HS256 JWT that travels in an ``HttpOnly``
cookie, so page scripts can never read it. The session slides: as long as it is
being used it is re-issued before it expires, while an idle session runs out.

Configuration mirrors what was there before — ``MIRROR_AUTH_USER`` and
``MIRROR_AUTH_PASSWORD``. Setting both enables the login; leaving either empty
keeps the whole deployment open. There is deliberately no separate secret to
configure: the signing key is derived from the credentials themselves, which
means sessions survive a container restart but a credential change invalidates
every token that is still out there.
"""

import asyncio
import hashlib
import os
import secrets
import time

import jwt
from fastapi import Request, Response

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
AUTH_USER = os.environ.get("MIRROR_AUTH_USER", "")
AUTH_PASSWORD = os.environ.get("MIRROR_AUTH_PASSWORD", "")

# Both halves are required. A half-configured deployment counts as "open"
# rather than as "locked with credentials nobody can satisfy".
AUTH_ENABLED = bool(AUTH_USER and AUTH_PASSWORD)

# auto | true | false — see .env.example. Anything unrecognised falls back to
# "auto" so a typo degrades to the safe-by-default behaviour instead of
# accidentally pinning the cookie to insecure.
COOKIE_SECURE_MODE = os.environ.get("MIRROR_COOKIE_SECURE", "auto").strip().lower()
if COOKIE_SECURE_MODE not in {"auto", "true", "false"}:
    COOKIE_SECURE_MODE = "auto"

SESSION_COOKIE = "mirror_session"

# Idle lifetime of a session. Re-issued once it is more than half used up
# (see `needs_refresh`), so an actively used session never expires mid-work.
SESSION_LIFETIME = 8 * 60 * 60  # 8 hours, in seconds

_ALGORITHM = "HS256"

# Domain separation for the derived key, not password hardening — the input is
# already the deployment's secret. Bumping the version invalidates all tokens.
_KDF_SALT = b"ps5-payloads-mirror/jwt-session/v1"
_KDF_ITERATIONS = 200_000


def _derive_secret() -> bytes:
    """Derive the token signing key from the configured credentials.

    Deterministic, so sessions survive a restart. Includes the username so that
    changing either half rotates the key and signs everyone out.
    """
    material = f"{AUTH_USER}\0{AUTH_PASSWORD}".encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", material, _KDF_SALT, _KDF_ITERATIONS)


# Derived once at import (~100 ms) and only when it can actually be used.
_SECRET = _derive_secret() if AUTH_ENABLED else b""


# --------------------------------------------------------------------------- #
# Credentials
# --------------------------------------------------------------------------- #
def verify_credentials(user: str, password: str) -> bool:
    """Constant-time credential check.

    Both comparisons always run — no short-circuit — so the response timing
    cannot reveal whether it was the username or the password that was wrong.
    Values are compared as bytes because `compare_digest` rejects `str` inputs
    that are not pure ASCII.
    """
    if not AUTH_ENABLED:
        return True
    user_ok = secrets.compare_digest(user.encode("utf-8"), AUTH_USER.encode("utf-8"))
    password_ok = secrets.compare_digest(
        password.encode("utf-8"), AUTH_PASSWORD.encode("utf-8")
    )
    return user_ok and password_ok


# --------------------------------------------------------------------------- #
# Tokens
# --------------------------------------------------------------------------- #
def issue_token(username: str) -> str:
    """Sign a session token for `username`."""
    now = int(time.time())
    return jwt.encode(
        {"sub": username, "iat": now, "exp": now + SESSION_LIFETIME},
        _SECRET,
        algorithm=_ALGORITHM,
    )


def decode_token(raw: str | None) -> dict | None:
    """Return the token's claims, or None if it is missing, altered or expired.

    `algorithms` is passed explicitly — that is what stops a token from
    dictating its own (or no) algorithm.
    """
    if not raw:
        return None
    try:
        return jwt.decode(raw, _SECRET, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None


def needs_refresh(claims: dict) -> bool:
    """True once a session is more than half used up.

    Refreshing on every request would attach a Set-Cookie to every response,
    including the scheduler's polling traffic; the halfway rule keeps an active
    session alive while bounding how often the cookie is rewritten.
    """
    issued_at = claims.get("iat")
    if not isinstance(issued_at, (int, float)):
        return True
    return (time.time() - issued_at) > (SESSION_LIFETIME / 2)


# --------------------------------------------------------------------------- #
# Cookie
# --------------------------------------------------------------------------- #
def cookie_secure(request: Request) -> bool:
    """Whether to mark the session cookie `Secure` for this request.

    In "auto" mode this follows the request scheme. Behind a reverse proxy that
    is only correct when uvicorn trusts the forwarded headers — see
    FORWARDED_ALLOW_IPS in docker-compose.yml.
    """
    if COOKIE_SECURE_MODE == "true":
        return True
    if COOKIE_SECURE_MODE == "false":
        return False
    return request.url.scheme == "https"


def set_session_cookie(response: Response, token: str, request: Request) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_LIFETIME,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(request),
        path="/",
    )


def clear_session_cookie(response: Response, request: Request) -> None:
    # The attributes must match those used when setting it, or the browser
    # keeps the original cookie alongside the deletion.
    response.delete_cookie(
        SESSION_COOKIE,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(request),
        path="/",
    )


# --------------------------------------------------------------------------- #
# Login throttling
#
# Deliberately a single global counter rather than per-IP state: every request
# arriving through the reverse proxy shares one source address, and the port is
# also reachable directly on the LAN where X-Forwarded-For is trivially forged.
# A delay (never a lockout) is what makes this safe to share — brute force is
# capped at a few attempts per second, but a correct password always gets
# through, so nobody can lock the legitimate user out.
# --------------------------------------------------------------------------- #
_BASE_DELAY = 0.5  # seconds, for the first failure
_MAX_DELAY = 5.0  # seconds, ceiling
_MAX_TRACKED_FAILURES = 16  # keeps 2**n from growing without bound

_failures = 0
_failures_lock = asyncio.Lock()


async def apply_login_delay() -> None:
    """Wait out the penalty accrued by previous failures, if any.

    Awaited *before* the credentials are checked, so a correct password is
    delayed exactly like a wrong one and the delay reveals nothing. The lock is
    not held across the sleep — it guards the counter, not the waiting.
    """
    async with _failures_lock:
        failures = _failures
    if failures:
        await asyncio.sleep(min(_BASE_DELAY * 2 ** (failures - 1), _MAX_DELAY))


async def register_login_failure() -> None:
    global _failures
    async with _failures_lock:
        _failures = min(_failures + 1, _MAX_TRACKED_FAILURES)


async def reset_login_failures() -> None:
    global _failures
    async with _failures_lock:
        _failures = 0
