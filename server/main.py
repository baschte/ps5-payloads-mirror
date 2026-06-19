"""FastAPI backend for the PS5 payloads mirror.

Wraps the reusable logic in ``mirror_core`` behind a small JSON API and serves
the built React frontend (``web/dist``) as static files so the whole thing runs
as a single process / single container.

Path operations that touch the network or filesystem are declared as plain
``def`` (not ``async def``) so FastAPI runs them in a worker threadpool and the
event loop is never blocked.
"""

import base64
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Path as PathParam, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import mirror_core
from mirror_core import DuplicateError, MirrorError, NotFoundError, ZipExtractNeeded
from server import git_ops
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
# Optional HTTP Basic Auth
#
# When MIRROR_AUTH_USER and MIRROR_AUTH_PASSWORD are both set, the UI and the
# management API require Basic Auth. The public, read-only payloads feed
# (/payloads.json) and the health check stay open so the mirror can be consumed
# anonymously and the container healthcheck keeps working.
# --------------------------------------------------------------------------- #
AUTH_USER = os.environ.get("MIRROR_AUTH_USER", "")
AUTH_PASSWORD = os.environ.get("MIRROR_AUTH_PASSWORD", "")
AUTH_ENABLED = bool(AUTH_USER and AUTH_PASSWORD)
PUBLIC_PATHS = frozenset({"/payloads.json", "/api/health"})


def _credentials_ok(header: str | None) -> bool:
    if not header or not header.startswith("Basic "):
        return False
    try:
        user, _, password = base64.b64decode(header[6:]).decode("utf-8").partition(":")
    except (ValueError, UnicodeDecodeError):
        return False
    # Constant-time comparison to avoid leaking length/content via timing.
    return secrets.compare_digest(user, AUTH_USER) and secrets.compare_digest(
        password, AUTH_PASSWORD
    )


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    if not AUTH_ENABLED or request.url.path in PUBLIC_PATHS:
        return await call_next(request)
    if _credentials_ok(request.headers.get("Authorization")):
        return await call_next(request)
    return Response(
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="Payloads Mirror"'},
    )


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class Payload(BaseModel):
    """A mirrored payload. Mirrors the shape stored in payloads.json."""

    model_config = {"extra": "allow"}

    name: str
    filename: str | None = None
    url: str | None = None
    source: str | None = None
    source_direct: str | None = None
    asset_pattern: str | None = None
    extract_file: str | None = None
    description: str | None = None
    last_update: str | None = None
    version: str | None = None
    checksum: str | None = None


class AddPayloadRequest(BaseModel):
    url: str = Field(description="Release URL of the upstream repo (GitHub or Gitea).")
    description: str = ""
    extract_file: str | None = Field(
        default=None,
        description="Internal .elf path to extract when the asset is a ZIP with multiple .elf files.",
    )


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
    if isinstance(exc, ZipExtractNeeded):
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
            return mirror_core.add_payload(req.url, req.description, req.extract_file)
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
