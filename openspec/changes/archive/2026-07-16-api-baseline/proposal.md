## Why

The project has specs for four narrow, previously-changed behaviors
(`asset-candidate-selection`, `mirror-editing`, `mirror-reordering`,
`mirror-visibility`), but the core management API that they all sit on top of
— adding/listing/updating/removing mirrors, the public payloads feed, title
management, optional auth, scheduled auto-updates, and git publish — has
never been captured as a spec. There is no single source of truth for what
the API in [server/main.py](server/main.py) actually does today, so future
changes have nothing to diff against and no shared vocabulary for its
requirements. This proposal documents the API exactly as it currently exists
in code — every route, request/response shape, status code, and behavior —
with no changes to the running system.

## What Changes

- Document the existing, already-shipped API surface as baseline requirements
  (no behavior changes to the running system). No new endpoints, no removed
  endpoints, no schema changes.

## API Reference (current state, as implemented)

Base app: FastAPI, `title="PS5 Payloads Mirror"`, `version="1.0.0"`
([server/main.py:43](server/main.py)). All mutating operations on the
mirror data acquire `mirror_core.DATA_LOCK`, a process-wide `threading.Lock`,
so no two writes (manual API calls, scheduled updates, auto-publish) can
race ([mirror_core.py:30](mirror_core.py)).

### Authentication (applies to every route below)

Optional HTTP Basic Auth, enforced by a global middleware
([server/main.py:94-103](server/main.py)):

- Enabled only when both `MIRROR_AUTH_USER` and `MIRROR_AUTH_PASSWORD`
  environment variables are set (`AUTH_ENABLED`).
- When enabled, every request must carry a valid `Authorization: Basic
  <base64(user:password)>` header, checked with `secrets.compare_digest`
  (constant-time), **except** two always-public paths: `/payloads.json` and
  `/api/health` (`PUBLIC_PATHS`).
- On missing/invalid credentials: `401` with header
  `WWW-Authenticate: Basic realm="Payloads Mirror"`.
- When either env var is unset, auth is fully disabled and every route is
  open.

### Collection title

**`GET /api/title`**
Returns `{ "name": string }` — the current collection title
(`mirror_core.get_title()`).

**`PUT /api/title`**
Body: `{ "name": string }`, `name` constrained to length 1–120
(`min_length=1, max_length=120` on the `CollectionTitle` model; a violating
body is rejected by FastAPI/Pydantic with `422` before the handler runs).
Persists the new title (`mirror_core.set_title`, trimmed; falls back to the
default title if the trimmed value is empty) under `DATA_LOCK` and returns
the stored `{ "name": string }`.

### Mirror listing and public feed

**`GET /api/payloads`**
Returns `list[Payload]` — every stored mirror, visible and hidden,
merged and sorted by `sort_order` (`mirror_core.load_payloads()`).

**`GET /payloads.json`** (`include_in_schema=False`, i.e. hidden from the
OpenAPI docs)
Serves the exact on-disk `payloads.json` file
(`mirror_core.JSON_FILE`) as `application/json`, with
`Access-Control-Allow-Origin: *` and `Cache-Control: no-cache`. Contains
only **visible** mirrors (hidden ones live in the separate,
never-served `hidden_payloads.json`). Always reachable without
authentication (see above).

**`Payload` model** (`extra: "allow"` — unknown fields are preserved,
not rejected):
```
name: str
filename: str | None
url: str | None
source: str | None
source_direct: str | None
asset_pattern: str | None
extract_file: str | None
description: str | None
last_update: str | None
version: str | None
checksum: str | None
sort_order: int | None
hidden: bool = False
```

### Adding a mirror

**`POST /api/payloads`** → `201 Created`, returns `Payload`

Body (`AddPayloadRequest`):
```
url: str                    # required, GitHub or Gitea release URL
description: str = ""
asset_name: str | None      # pin a specific top-level release asset
extract_file: str | None    # pin a specific in-zip .elf/.bin member
```

Behavior (`mirror_core.add_payload`, under `DATA_LOCK`):
1. Rejects an empty/whitespace-only `url` (`400`).
2. Parses `(domain, owner, repo)` from the URL; unparsable URL → `400`.
3. Fetches the latest release (`gh api .../releases/latest` for
   `github.com`; Gitea API `.../releases/latest` for any other domain),
   falling back to the newest non-draft release from the full listing if
   there is no stable "latest". No release found → `400`.
4. Resolves exactly one candidate asset (and, for a ZIP, one member) from
   the release's assets:
   - If the URL itself names a specific asset filename (`...name.elf|bin|zip`)
     that exists in the release and no explicit `asset_name` was given, that
     filename is used automatically.
   - Otherwise uses `asset_name`/`extract_file` if given, or auto-selects
     when exactly one plausible `.elf`/`.bin`/`.zip` asset (and, for a lone
     ZIP, exactly one plausible internal member) exists.
   - More than one plausible candidate and no explicit pick →
     `422` with `{"message": str, "candidates": [{"asset_name", "member_name", "label"}, ...]}`
     (`AmbiguousAssetError`).
5. Rejects if a mirror with the same derived `source` URL
   (`https://{domain}/{owner}/{repo}/releases`) already exists → `409`
   (`DuplicateError`).
6. Downloads the asset (extracting the chosen ZIP member if applicable) into
   `PAYLOADS_DIR/{repo}_{version}.{ext}`, computes its SHA-256 checksum,
   assigns the next `sort_order`, sets `hidden: false`, appends it, persists,
   and returns the new `Payload`.

### Listing candidates for an existing mirror (read-only)

**`GET /api/payloads/{name}/candidates`**
Returns `list[CandidateModel]` (`{asset_name: str, member_name: str | None,
label: str}`) — the current release's plausible assets/members for the
named mirror's **existing, unchanged** source, without persisting anything.
Lets the edit UI offer an asset/file switch without a source URL change.
`404` if `name` doesn't exist; `400` if the source can't be resolved.

### Reordering mirrors

**`PUT /api/payloads/reorder`** → returns `list[Payload]`
(registered **before** the `/{name}` routes below so the literal path
segment `reorder` is never captured as a `{name}` path parameter)

Body (`ReorderRequest`): `{ "names": list[str] }` — must contain every
currently known mirror name (visible **and** hidden), each exactly once, in
the desired order. Under `DATA_LOCK`:
- Duplicate name in the list → `400`.
- Set of given names ≠ set of current mirror names → `400`.
- Otherwise assigns `sort_order = (position + 1) * 10` to every mirror,
  persists, and returns the merged, re-sorted list.

### Editing a mirror

**`PUT /api/payloads/{name}`** → returns `Payload`

Body (`EditPayloadRequest`, all fields optional):
```
url: str | None            # new source release URL, if changing source
description: str | None
asset_name: str | None
extract_file: str | None
```

Behavior (`mirror_core.edit_payload`, under `DATA_LOCK`); `404` if `name`
doesn't exist:

- **Source unchanged** (`url` omitted or equal to the stored `source`):
  - `description`, if given, is patched in place with no network call.
  - If `asset_name`/`extract_file` name a different candidate than
    currently stored, the source's latest release is re-fetched and that
    candidate is downloaded/extracted (old local file removed if the
    filename changes), replacing the asset-derived fields — the source
    itself does not change.
  - `sort_order` and `hidden` are always preserved unchanged.
- **Source changed** (`url` given and different from stored `source`):
  - Re-resolves exactly like `add_payload` (candidate ambiguity → `422`
    with the same shape as above).
  - Rejects if the **new** source matches a *different* existing mirror
    (excluding the item being edited itself) → `409`.
  - Replaces the item in place at its current list position — name,
    filename, url, source, version, checksum etc. may all change — while
    still carrying over the existing `sort_order` and `hidden` status.
  - Deletes the old local file if the filename changed.

### Setting hidden/visible

**`PUT /api/payloads/{name}/hidden`** → returns `Payload`
Body (`SetHiddenRequest`): `{ "hidden": bool }`. Sets the mirror's `hidden`
flag (moving it between `payloads.json` and `hidden_payloads.json` on the
next write) under `DATA_LOCK`. `404` if `name` doesn't exist. Hidden mirrors
are excluded from `/payloads.json`, from the README, and from git commits.

### Updating mirrors

**`POST /api/payloads/update-all`** → returns `list[UpdateAllResult]`
(`UpdateAllResult` = `UpdateResult` + `name: str`, where `UpdateResult` =
`{updated: bool, item: Payload, message: str}`)

Under `DATA_LOCK`, checks every stored mirror against its source's latest
release in turn; a single mirror's failure (`MirrorError`) is caught and
reported as `updated: false` with the error message, without aborting the
rest. Also refreshes every item's `url` field from its current `filename`
before persisting once at the end.

**`POST /api/payloads/{name}/update`** → returns `UpdateResult`
Checks a single named mirror against its source's latest release under
`DATA_LOCK`. `404` if `name` doesn't exist. Cases:
- No `source` stored → not updated, message `"No source to check."`.
- Source URL unparsable → not updated, message `"Could not parse source URL."`.
- No release/assets found upstream → not updated, message `"No release/assets found upstream."`.
- Previously-selected asset (`asset_pattern`/`extract_file`) no longer
  present upstream → not updated, message `"Previously selected asset no longer found upstream."`.
- Version, filename, and mirror-release-asset-name all already match →
  not updated, message `"Already up to date ({version})."` (still persists
  if the resolved candidate identity itself changed, e.g. legacy migration).
- Otherwise downloads the new asset, updates `version`, `filename`, `url`,
  `source_direct`, `last_update`, `checksum`, `asset_pattern`,
  `extract_file`, deletes the old local file if the filename changed, and
  returns `updated: true` with message `"Updated to {version}."`.

### Removing a mirror

**`DELETE /api/payloads/{name}`** → `204 No Content`
Deletes the mirror's local file (if present) and removes it from the stored
data under `DATA_LOCK`. `404` if `name` doesn't exist.

### Scheduler

In-process `asyncio` task (`server/scheduler.py`), started/stopped in the
app's `lifespan`. Config (`enabled`, `interval_hours`) persists to
`scheduler_config.json` and survives restarts. Defaults:
`enabled=True`, `interval_hours=4`, clamped to `[1, 24]`
(`MIN_INTERVAL_HOURS`, `MAX_INTERVAL_HOURS`). A scheduled run acquires the
same `DATA_LOCK` as manual mutations, so it can never overlap them, and runs
the blocking update work in a worker thread so the event loop isn't
blocked. An unexpected error during a run is caught, recorded in
`last_summary` as `"Update failed: {e}"`, and does not kill the scheduler
loop.

**`GET /api/scheduler`** → `SchedulerStatus`:
```
enabled: bool
interval_hours: int
is_running: bool
last_run: str | None       # ISO 8601, UTC
next_run: str | None       # ISO 8601, UTC; null when disabled
last_summary: str | None
```

**`PUT /api/scheduler`** → `SchedulerStatus`
Body (`SchedulerConfig`): `{ "enabled": bool, "interval_hours": int }`, with
`interval_hours` constrained `ge=1, le=24` at the Pydantic level (an
out-of-range value is rejected with `422` before reaching the handler; the
scheduler's own internal `_clamp` is a second line of defense for
values arriving outside HTTP, e.g. from a stale config file). Persists the
new config, recomputes `next_run` from now, and wakes the scheduler loop
immediately so a changed interval/enablement takes effect without waiting
out the previous interval.

**`POST /api/scheduler/run-now`** → `SchedulerStatus`
Triggers an update run immediately in the background. No-op (does not start
a second concurrent run) if one is already in progress; either way returns
the current status.

### Git publish

**`GET /api/git/status`** → `GitStatus`: `{ enabled: bool, pending: bool }`
`enabled` = `git_ops.push_enabled()` (all four of `GIT_USERNAME`,
`GIT_PASSWORD`, `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL` set, `git` available,
and the working directory is a git repo). `pending` = `enabled` and
`payloads.json`/`README.md` have uncommitted changes
(`git status --porcelain`).

**`POST /api/git/push`** → `GitPushResult`:
`{ committed: bool, pushed: bool, message: str }`
Under `DATA_LOCK`, calls `git_ops.commit_and_push()`:
1. Not configured / git unavailable / not a repo → `400` with an
   explanatory message (`GitError`).
2. Aborts any rebase left in progress by a previous failed attempt.
3. Stages exactly `payloads.json` and `README.md` (never
   `hidden_payloads.json` — hidden mirrors are never committed or pushed).
4. Nothing staged (no diff) → returns `{committed: false, pushed: false,
   message: "No changes to publish."}` without creating an empty commit.
5. Commits with message `"Update payloads metadata via web UI"` using the
   configured author name/email.
6. `git pull --rebase -X theirs` onto the current branch's remote (the
   `-X theirs` auto-resolves in favor of the local commit — this is the
   generated-artifact "publish my state" case, since a daily GitHub Action
   may also write these files). Conflict/failure that can't rebase → aborts
   the rebase (commit stays intact), raises `GitError` → `400`.
7. Pushes `HEAD:{branch}` to `origin` (resolved to an HTTPS URL regardless
   of whether `origin` is configured as SSH or HTTPS). Failure → `400`.
8. Success → `{committed: true, pushed: true, message: "Committed & pushed
   to {branch}."}`.
9. Never force-pushes. The password is supplied to git only via a
   credential-helper shell function reading it from the subprocess
   environment (never on disk, never in argv, never in the remote URL),
   and is scrubbed (`***`) from any error text returned to the client.

**`GET /api/git/auto-publish`** → `AutoPublishStatus`:
```
enabled: bool         # AUTO_PUBLISH_ENABLED (default on) AND push_enabled()
delay_seconds: int    # AUTO_PUBLISH_DELAY_SECONDS, default 60
is_publishing: bool
pending: bool         # debounce timer currently armed
last_result: str | None
```
Auto-publish mechanism: every successful write of `payloads.json`
(manual edit, scheduled update, title change — any call through
`mirror_core`'s post-write hooks) (re)arms a single debounce timer.
Multiple writes inside the delay window coalesce into one publish. When the
timer fires, publish runs in a worker thread under `DATA_LOCK` (same path as
manual push); if a publish is still running when the timer fires again, the
timer re-arms so the new changes get their own publish once the current one
finishes. Disabled entirely via `AUTO_PUBLISH_ENABLED=0` (or `false`/empty),
or when git publish itself isn't configured.

### Health check

**`GET /api/health`** → `{ "status": "ok", "payloads": int }` — always
reachable without authentication. `payloads` is the current count of
stored mirrors (visible + hidden).

### Error mapping (`mirror_core.MirrorError` subclasses → HTTP status)

| Exception | Status | Notes |
| --- | --- | --- |
| `DuplicateError` | 409 | source URL already mirrored |
| `NotFoundError` | 404 | no mirror with the given name |
| `AmbiguousAssetError` | 422 | body: `{"message": str, "candidates": [...]}` |
| `MirrorError` (base/other) | 400 | body: `str(exc)` |
| `git_ops.GitError` | 400 | body: `str(exc)` |
| Pydantic validation failure (e.g. title length, interval range) | 422 | FastAPI default, before the handler runs |

### Static frontend (mounted last, so `/api/*` and the routes above always
win)

If a built frontend directory is found (`WEB_DIST_DIR` env var, else
`/opt/web/dist`, else the in-repo `web/dist`), `/assets` is mounted as
static files and any other unmatched path (`GET /{full_path:path}`,
hidden from the OpenAPI docs) serves that path's file if it exists, else
falls back to `index.html` (SPA routing fallback).

## Capabilities

### New Capabilities
- `mirror-management-api`: Core CRUD lifecycle for mirrored payloads (add,
  list, update-one, update-all, remove) and the public `/payloads.json` feed.
- `collection-title`: Getting and setting the mirror collection's display
  title.
- `api-authentication`: Optional HTTP Basic Auth protecting the management
  API while keeping the public feed and health check accessible without
  credentials.
- `update-scheduler`: Configuring and running the in-process periodic
  auto-update job.
- `git-publish`: Committing and pushing mirror data changes to the configured
  git remote, on demand and via auto-publish.

### Modified Capabilities
(none — this change only adds baseline specs for previously undocumented
behavior; it does not alter requirements in `asset-candidate-selection`,
`mirror-editing`, `mirror-reordering`, or `mirror-visibility`)

## Impact

- Affected code: none (documentation-only change against
  [server/main.py](server/main.py), [mirror_core.py](mirror_core.py),
  [server/scheduler.py](server/scheduler.py),
  [server/auto_publish.py](server/auto_publish.py),
  [server/git_ops.py](server/git_ops.py)).
- Affected specs: adds five new `specs/<name>/spec.md` files; no existing spec
  files are modified.
- Establishes the baseline that future API changes (new endpoints, auth
  changes, scheduler behavior changes) can be proposed as deltas against.
