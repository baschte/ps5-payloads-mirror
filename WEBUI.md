# Web UI

A small React + FastAPI app to manage the mirror from the browser: **add**,
**update** (single or all), and **remove** mirrored payloads. All actions are
local — they edit `payloads.json`, the `payloads/` directory and `README.md`.
Publishing to GitHub Releases stays the job of the existing daily GitHub Action.

## Architecture

- **`mirror_core.py`** — reusable, non-interactive logic (shared by the CLI scripts and the API).
- **`server/main.py`** — FastAPI backend; also serves the built frontend.
- **`web/`** — Vite + React + TypeScript frontend, styled with **Tailwind CSS v4** (CSS-first `@theme` tokens) and bundled Fontsource fonts (Bricolage Grotesque / Hanken Grotesk / JetBrains Mono) so it works fully offline. Includes a **light/dark mode** toggle (persisted to `localStorage`, respects the OS preference, no flash on load) driven by `.dark` CSS-variable overrides.

The CLI scripts (`add_payload.py`, `update_payloads.py`) and the GitHub Action
keep working unchanged — they now just call into `mirror_core`.

## Scheduler

An in-process scheduler runs a full update automatically. It lives inside the
FastAPI process (a single asyncio task), so no external cron is needed — it fits
the single-container deployment. Defaults: **enabled, every 4 hours**. The
interval is adjustable **1–24 hours** from the UI ("Automatic updates" panel)
and persisted to `scheduler_config.json` so it survives restarts. Scheduled and
manual operations are serialized via a shared lock, and `payloads.json` is
written atomically, so concurrent runs can never corrupt or drop entries.

## Authentication (optional)

The UI and the management API can be protected with HTTP Basic Auth. Set **both**
env vars to enable a login:

```
MIRROR_AUTH_USER=admin
MIRROR_AUTH_PASSWORD=change-me
```

- When set, `/` (UI), `/assets/*` and `/api/*` require the credentials (the
  browser shows a native login dialog and reuses the credentials for the API).
- **Always public**, even with auth on: `GET /payloads.json` (the read-only feed)
  and `GET /api/health` (so the container healthcheck keeps working).
- When the vars are empty/unset, everything stays open (default).

## Publish to GitHub (optional)

A **Publish** button commits `payloads.json` + `README.md`, runs `git pull
--rebase`, then pushes — so you can persist edits made in the UI straight to the
GitHub repo. Enable it by setting **all four** env vars:

```
GIT_USERNAME=your-github-user
GIT_PASSWORD=ghp_xxx          # a GitHub PAT with repo write access (NOT your password)
GIT_AUTHOR_NAME=Your Name
GIT_AUTHOR_EMAIL=you@example.com
```

Requirements & behaviour:
- The container needs the **full git working tree**, so `docker-compose.yml`
  bind-mounts the whole repo (`.:/app`). The built frontend lives at
  `/opt/web/dist` in the image, so the mount doesn't hide it.
- Always runs `git pull --rebase <branch>` before pushing; on conflict it does
  `git rebase --abort` and returns an error (never a force-push).
- The token is passed to git via a one-shot credential helper from the
  environment — never written to disk, never in argv, never in the remote URL,
  and any git output is scrubbed of it before reaching the client.
- The endpoint sits behind the Basic Auth above. Use HTTPS in production.
- When the four vars aren't set (or it isn't a git repo), the button is hidden.

### Auto-publish

When publishing is configured, every change to `payloads.json` — whether made
manually in the UI or found by the scheduler — automatically triggers a commit &
push **after a short debounce window** (default 60s). Several changes inside the
window coalesce into a single publish. The manual **Publish** button still works
as an immediate override.

Tune it with env vars (both optional):

```
AUTO_PUBLISH_DELAY_SECONDS=60   # debounce window in seconds (default 60)
AUTO_PUBLISH_ENABLED=0          # set to 0/false to disable auto-publish entirely
```

The publish runs under the same data lock as the manual one, so it never
overlaps an in-flight edit or scheduled update. `GET /api/git/auto-publish`
reports its state.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/payloads` | List all mirrors |
| `POST` | `/api/payloads` | Add a mirror `{url, description?, extract_file?}` |
| `POST` | `/api/payloads/{name}/update` | Update one mirror |
| `POST` | `/api/payloads/update-all` | Update every mirror |
| `DELETE` | `/api/payloads/{name}` | Remove a mirror (local file + JSON) |
| `GET` | `/api/scheduler` | Scheduler status (enabled, interval, last/next run) |
| `PUT` | `/api/scheduler` | Set `{enabled, interval_hours}` (1–24) |
| `POST` | `/api/scheduler/run-now` | Trigger an update immediately |
| `GET` | `/api/git/status` | Whether the Publish button is enabled |
| `POST` | `/api/git/push` | Commit payloads.json + README.md, rebase, push |
| `GET` | `/api/git/auto-publish` | Auto-publish status (enabled, delay, pending, last result) |

## Run locally (dev)

Two terminals:

```bash
# 1. Backend (with hot reload) — needs `gh auth login` for github.com sources
python -m venv .venv && .venv/bin/pip install "fastapi[standard]"
.venv/bin/fastapi dev server/main.py        # http://localhost:8000

# 2. Frontend dev server (proxies /api -> :8000)
cd web && npm install && npm run dev         # http://localhost:5173
```

## Run as a single container

### Docker Compose (recommended)

```bash
cp .env.example .env          # set GH_TOKEN (and optionally PORT)
docker compose up -d --build  # build + start in the background
docker compose logs -f        # follow logs
docker compose down           # stop & remove
```

The UI is then on `http://localhost:8000` (or `PORT`). `docker-compose.yml`
bind-mounts `payloads.json`, `README.md` and `payloads/` so the mirror data
persists on the host across rebuilds, and adds a `/api/health` healthcheck +
`restart: unless-stopped`.

### Plain Docker

```bash
docker build -t ps5-payloads-mirror .
docker run -p 8000:8000 -e GH_TOKEN=<your_github_token> ps5-payloads-mirror
```

`GH_TOKEN` (or `GITHUB_TOKEN`) is needed so the `gh` CLI can read release
metadata from github.com. Non-GitHub hosts (e.g. Gitea) are reached directly.
