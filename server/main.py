"""FastAPI backend for the PS5 payloads mirror.

Wraps the reusable logic in ``mirror_core`` behind a small JSON API and serves
the built React frontend (``web/dist``) as static files so the whole thing runs
as a single process / single container.

Path operations that touch the network or filesystem are declared as plain
``def`` (not ``async def``) so FastAPI runs them in a worker threadpool and the
event loop is never blocked.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Path as PathParam, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import mirror_core
from mirror_core import AmbiguousAssetError, DuplicateError, MirrorError, NotFoundError
from server import auth, git_ops
from server.auto_publish import AutoPublisher
from server.scheduler import MAX_INTERVAL_HOURS, MIN_INTERVAL_HOURS, Scheduler

scheduler = Scheduler()
auto_publisher = AutoPublisher()


@asynccontextmanager
async def lifespan(app: FastAPI):
    auto_publisher.start()
    scheduler.start()
    yield
    await scheduler.stop()
    await auto_publisher.stop()


app = FastAPI(title="PS5 Payloads Mirror", version="1.0.0", lifespan=lifespan)


def _resolve_dist_dir() -> Path:
    """Locate the built frontend.

    Prefers /opt/web/dist (baked into the image, outside /app) so it isn't
    shadowed when the whole repo is bind-mounted at /app. Falls back to the
    in-repo build for local dev.
    """
    candidates = [
        os.environ.get("WEB_DIST_DIR"),
        "/opt/web/dist",
        str(mirror_core.BASE_DIR / "web" / "dist"),
    ]
    for c in candidates:
        if c and Path(c).is_dir():
            return Path(c)
    return Path("/opt/web/dist")


DIST_DIR = _resolve_dist_dir()


# --------------------------------------------------------------------------- #
# Optional session authentication
#
# When MIRROR_AUTH_USER and MIRROR_AUTH_PASSWORD are both set, the management
# API requires a session established through the login screen (see server/auth).
# Everything the browser needs in order to *render* that screen stays public —
# the SPA shell and its assets — as do the raw payloads feed (consumed by third
# parties) and the health check (used by the container healthcheck).
#
# The guard is a middleware rather than a per-route dependency so that it is
# fail-closed: a newly added /api endpoint is protected without anyone having to
# remember to protect it.
# --------------------------------------------------------------------------- #

# Not under /api/, but still management surface rather than app shell.
_PROTECTED_NON_API = frozenset({"/docs", "/redoc", "/openapi.json"})


def _is_public(path: str) -> bool:
    """Whether `path` is reachable without a session.

    Public: the SPA shell and its assets, /payloads.json, the health check, and
    the auth endpoints themselves (logging out and asking "am I signed in?" must
    work precisely when there is no valid session).
    """
    if path in _PROTECTED_NON_API:
        return False
    if not path.startswith("/api/"):
        return True
    return path == "/api/health" or path.startswith("/api/auth/")


@app.middleware("http")
async def session_auth(request: Request, call_next):
    if not auth.AUTH_ENABLED or _is_public(request.url.path):
        return await call_next(request)

    claims = auth.decode_token(request.cookies.get(auth.SESSION_COOKIE))
    if claims is None:
        # Plain JSON 401 — deliberately no WWW-Authenticate, which would make
        # the browser pop its native credential dialog over the login screen.
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    response = await call_next(request)
    # Slide the session forward while it is being used (see auth.needs_refresh).
    if response.status_code < 400 and auth.needs_refresh(claims):
        auth.set_session_cookie(
            response, auth.issue_token(str(claims.get("sub", auth.AUTH_USER))), request
        )
    return response


# --------------------------------------------------------------------------- #
# Auth endpoints
# --------------------------------------------------------------------------- #
class LoginRequest(BaseModel):
    username: str
    password: str


class SessionStatus(BaseModel):
    """What the frontend needs to decide between login screen and app shell."""

    authenticated: bool
    auth_enabled: bool
    username: str | None = None


@app.post("/api/auth/login")
async def login(req: LoginRequest, request: Request, response: Response) -> SessionStatus:
    """Exchange credentials for a session cookie.

    Declared ``async`` on purpose: the brute-force delay is awaited, so it parks
    the coroutine instead of tying up a threadpool worker.
    """
    if not auth.AUTH_ENABLED:
        # Nothing to log in to. Succeed rather than error, so a client that
        # tries anyway is never stuck on a login screen it cannot get past.
        return SessionStatus(authenticated=True, auth_enabled=False)

    # Applied before verification so a correct password waits exactly as long
    # as a wrong one, and the delay itself leaks nothing.
    await auth.apply_login_delay()

    if not auth.verify_credentials(req.username, req.password):
        await auth.register_login_failure()
        # One generic message: never reveal which half was wrong.
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    await auth.reset_login_failures()
    auth.set_session_cookie(response, auth.issue_token(auth.AUTH_USER), request)
    return SessionStatus(authenticated=True, auth_enabled=True, username=auth.AUTH_USER)


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> SessionStatus:
    """End the session. Succeeds even without one, so it is always safe to call."""
    auth.clear_session_cookie(response, request)
    return SessionStatus(authenticated=False, auth_enabled=auth.AUTH_ENABLED)


@app.get("/api/auth/me")
def session_status(request: Request) -> SessionStatus:
    """Report the caller's session so the frontend knows what to render."""
    if not auth.AUTH_ENABLED:
        return SessionStatus(authenticated=True, auth_enabled=False)
    claims = auth.decode_token(request.cookies.get(auth.SESSION_COOKIE))
    if claims is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return SessionStatus(
        authenticated=True, auth_enabled=True, username=str(claims.get("sub", ""))
    )


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class Payload(BaseModel):
    """A mirrored payload. Mirrors the shape stored in payloads.json."""

    model_config = {"extra": "allow"}

    name: str
    title: str | None = None
    filename: str | None = None
    url: str | None = None
    source: str | None = None
    source_direct: str | None = None
    asset_pattern: str | None = None
    extract_file: str | None = None
    description: str | None = None
    category: str | None = None
    last_update: str | None = None
    version: str | None = None
    checksum: str | None = None
    sort_order: int | None = None
    hidden: bool = False


class AddPayloadRequest(BaseModel):
    url: str = Field(description="Release URL of the upstream repo (GitHub or Gitea).")
    description: str = ""
    title: str | None = Field(default=None, description="Display title, if different from the derived name.")
    category: str | None = Field(default=None, description="Single free-text category for this mirror.")
    asset_name: str | None = Field(
        default=None,
        description="Top-level release asset filename to use, when the release has multiple candidates.",
    )
    extract_file: str | None = Field(
        default=None,
        description="Internal .elf/.bin path to extract when the chosen asset is a ZIP with multiple members.",
    )


class EditPayloadRequest(BaseModel):
    url: str | None = Field(default=None, description="New source release URL, if changing the source.")
    description: str | None = Field(default=None, description="New description, if changing it.")
    title: str | None = Field(default=None, description="New display title, if changing it.")
    category: str | None = Field(
        default=None,
        description="New category, if changing it. Omit to leave unchanged; send an empty string to clear it.",
    )
    asset_name: str | None = Field(
        default=None,
        description="Top-level release asset filename to use, when the release has multiple candidates.",
    )
    extract_file: str | None = Field(
        default=None,
        description="Internal .elf/.bin path to extract when the chosen asset is a ZIP with multiple members.",
    )


class CandidateModel(BaseModel):
    asset_name: str
    member_name: str | None = None
    label: str


class ReorderRequest(BaseModel):
    names: list[str] = Field(
        description="Every known mirror name (visible and hidden), exactly once, in the desired order."
    )


class SetHiddenRequest(BaseModel):
    hidden: bool


class UpdateResult(BaseModel):
    updated: bool
    item: Payload
    message: str


class UpdateAllResult(UpdateResult):
    name: str


class SchedulerStatus(BaseModel):
    enabled: bool
    interval_hours: int
    is_running: bool
    last_run: str | None = None
    next_run: str | None = None
    last_summary: str | None = None


class SchedulerConfig(BaseModel):
    enabled: bool
    interval_hours: int = Field(
        ge=MIN_INTERVAL_HOURS,
        le=MAX_INTERVAL_HOURS,
        description="Hours between automatic updates (1–24).",
    )


# --------------------------------------------------------------------------- #
# Error handling helper
# --------------------------------------------------------------------------- #
def _raise_http(exc: MirrorError) -> None:
    if isinstance(exc, DuplicateError):
        raise HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, AmbiguousAssetError):
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "candidates": exc.candidates},
        )
    raise HTTPException(status_code=400, detail=str(exc))


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
class CollectionTitle(BaseModel):
    name: str = Field(min_length=1, max_length=120)


@app.get("/api/title")
def read_title() -> CollectionTitle:
    return CollectionTitle(name=mirror_core.get_title())


@app.put("/api/title")
def update_title(body: CollectionTitle) -> CollectionTitle:
    with mirror_core.DATA_LOCK:
        return CollectionTitle(name=mirror_core.set_title(body.name))


@app.get("/api/payloads")
def list_payloads() -> list[Payload]:
    return mirror_core.load_payloads()


@app.get("/payloads.json", include_in_schema=False)
def raw_payloads_json() -> FileResponse:
    """Public, raw payloads.json feed served under a clean URL.

    Same data as ``/api/payloads`` but as the exact file on disk, with CORS
    open so it can be consumed from other origins.
    """
    return FileResponse(
        mirror_core.JSON_FILE,
        media_type="application/json",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-cache",
        },
    )


@app.post("/api/payloads", status_code=201)
def add_payload(req: AddPayloadRequest) -> Payload:
    try:
        with mirror_core.DATA_LOCK:
            return mirror_core.add_payload(
                req.url, req.description, req.extract_file,
                asset_name=req.asset_name, title=req.title, category=req.category,
            )
    except MirrorError as e:
        _raise_http(e)


@app.get("/api/payloads/{name}/candidates")
def list_payload_candidates(name: Annotated[str, PathParam()]) -> list[CandidateModel]:
    """Read-only: the current release's candidate files for an existing
    mirror's (unchanged) source, so the edit UI can offer an asset/file
    switch without requiring a source URL change."""
    try:
        return mirror_core.list_candidates_for_payload(name)
    except MirrorError as e:
        _raise_http(e)


@app.put("/api/payloads/reorder")
def reorder_payloads(req: ReorderRequest) -> list[Payload]:
    """Persist a full manual reordering across both visible and hidden mirrors.

    Registered before the /{name} routes below so "reorder" is never matched
    as a path parameter.
    """
    try:
        with mirror_core.DATA_LOCK:
            return mirror_core.reorder_payloads(req.names)
    except MirrorError as e:
        _raise_http(e)


@app.put("/api/payloads/{name}")
def edit_payload(name: Annotated[str, PathParam()], req: EditPayloadRequest) -> Payload:
    try:
        with mirror_core.DATA_LOCK:
            return mirror_core.edit_payload(
                name,
                url=req.url,
                description=req.description,
                title=req.title,
                category=req.category,
                extract_file=req.extract_file,
                asset_name=req.asset_name,
            )
    except MirrorError as e:
        _raise_http(e)


@app.put("/api/payloads/{name}/hidden")
def set_payload_hidden(name: Annotated[str, PathParam()], req: SetHiddenRequest) -> Payload:
    try:
        with mirror_core.DATA_LOCK:
            return mirror_core.set_hidden(name, req.hidden)
    except MirrorError as e:
        _raise_http(e)


@app.post("/api/payloads/update-all")
def update_all() -> list[UpdateAllResult]:
    with mirror_core.DATA_LOCK:
        return mirror_core.update_all()


@app.post("/api/payloads/{name}/update")
def update_payload(name: Annotated[str, PathParam()]) -> UpdateResult:
    try:
        with mirror_core.DATA_LOCK:
            return mirror_core.update_one(name)
    except MirrorError as e:
        _raise_http(e)


@app.delete("/api/payloads/{name}", status_code=204)
def delete_payload(name: Annotated[str, PathParam()]) -> None:
    try:
        with mirror_core.DATA_LOCK:
            mirror_core.remove_payload(name)
    except MirrorError as e:
        _raise_http(e)


# --------------------------------------------------------------------------- #
# Scheduler
# --------------------------------------------------------------------------- #
@app.get("/api/scheduler")
def get_scheduler() -> SchedulerStatus:
    return scheduler.status()


@app.put("/api/scheduler")
async def set_scheduler(config: SchedulerConfig) -> SchedulerStatus:
    return await scheduler.update_config(config.enabled, config.interval_hours)


@app.post("/api/scheduler/run-now")
async def run_scheduler_now() -> SchedulerStatus:
    return await scheduler.run_now()


# --------------------------------------------------------------------------- #
# Git publish
# --------------------------------------------------------------------------- #
class GitStatus(BaseModel):
    enabled: bool
    pending: bool


class GitPushResult(BaseModel):
    committed: bool
    pushed: bool
    message: str


@app.get("/api/git/status")
def git_status() -> GitStatus:
    enabled = git_ops.push_enabled()
    return GitStatus(enabled=enabled, pending=enabled and git_ops.has_changes())


@app.post("/api/git/push")
def git_push() -> GitPushResult:
    try:
        with mirror_core.DATA_LOCK:
            return GitPushResult(**git_ops.commit_and_push())
    except git_ops.GitError as e:
        raise HTTPException(status_code=400, detail=str(e))


class AutoPublishStatus(BaseModel):
    enabled: bool
    delay_seconds: int
    is_publishing: bool
    pending: bool
    last_result: str | None = None


@app.get("/api/git/auto-publish")
def auto_publish_status() -> AutoPublishStatus:
    return AutoPublishStatus(**auto_publisher.status())


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "payloads": len(mirror_core.load_payloads())}


# --------------------------------------------------------------------------- #
# Static frontend (mounted last so /api/* always wins)
# --------------------------------------------------------------------------- #
if DIST_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        """Serve the SPA: real files when present, else index.html for routing."""
        candidate = DIST_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST_DIR / "index.html")
