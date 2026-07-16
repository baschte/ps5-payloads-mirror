# PS5 Payloads Mirror

An automated mirror of useful payloads for the jailbroken PlayStation 5 – including a web UI for management, an automatic update scheduler, and an optional publish-to-GitHub workflow.

This project is a **fork/continuation** of [itsPLK/ps5-payloads-mirror](https://github.com/itsPLK/ps5-payloads-mirror) – see [Credits](#credits--thanks) at the end.

## Contents

- [What this project does](#what-this-project-does)
- [Architecture](#architecture)
- [Local setup](#local-setup)
- [Running with Docker](#running-with-docker)
- [Configuration (environment)](#configuration-environment)
- [Working with the mirror](#working-with-the-mirror)
- [Development with OpenSpec](#development-with-openspec)
- [Automation (GitHub Actions)](#automation-github-actions)
- [Available payloads](#available-payloads)
- [Support & Suggestions](#support--suggestions)
- [Credits & Thanks](#credits--thanks)

## What this project does

- Downloads PS5 payloads from GitHub/Git releases and mirrors them as its own release assets.
- Maintains a `payloads.json` with name, version, description, source, and download link.
- Provides a **web UI** to add, edit, reorder, hide, and manually update payloads.
- Updates payloads automatically via an internal scheduler or a GitHub Action.
- Can optionally commit and push changes back to GitHub automatically ("Publish to GitHub").

## Architecture

| Part | Technology | Purpose |
| --- | --- | --- |
| `mirror_core.py` | Python | Core logic: downloads, versioning, JSON maintenance, locking |
| `server/` | FastAPI | Backend API + serving the frontend |
| `web/` | React + TypeScript + Vite + Tailwind v4 | Web UI for managing mirrors |
| `add_payload.py` | Python CLI | Interactively add a new payload |
| `update_payloads.py` | Python CLI | Update all payloads (also used by the GitHub Action) |
| `openspec/` | Spec-Driven Development | Structured change process for new features |

Detailed API reference and architecture description: see [WEBUI.md](WEBUI.md).

## Local setup

**Requirements:** Python ≥ 3.10, Node.js ≥ 20, `git`, optionally the [`gh` CLI](https://cli.github.com/) for release metadata.

```bash
git clone <repo-url>
cd ps5-payloads-mirror
./start.sh
```

`start.sh` automatically handles:
1. Creates a `.venv` (if missing) and installs the backend via `pip install -e .`
2. Installs the frontend dependencies (`npm install` in `web/`)
3. Starts the backend (`uvicorn server.main:app --reload`, port `8000`) and the frontend (`npm run dev`, Vite, port `5173`) in parallel
4. Cleanly stops both processes on `Ctrl+C`

Afterwards:
- Web UI: [http://localhost:5173](http://localhost:5173)
- API directly: [http://localhost:8000](http://localhost:8000)

### Manual setup (without `start.sh`)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn server.main:app --reload --port 8000

# in a second terminal
cd web
npm install
npm run dev
```

## Running with Docker

```bash
cp .env.example .env   # adjust as needed
docker compose up -d --build
```

- Builds the frontend (`node:20-slim`) and bundles it with the Python backend (`python:3.12-slim`) into one image.
- The container always listens internally on port `8000`, mapped externally via `PORT` (default `8000`).
- Healthcheck runs against `/api/health`.
- The entire repo is mounted as a volume so data changes (`payloads.json`, Git publish) persist.

## Configuration (environment)

All variables are optional, see [.env.example](.env.example):

| Variable | Purpose |
| --- | --- |
| `GH_TOKEN` | GitHub token for the `gh` CLI (reading release metadata) |
| `PORT` | Host-side port, default `8000` |
| `MIRROR_TITLE` | Fallback collection title, used if none is set in `payloads.json` |
| `MIRROR_AUTH_USER` / `MIRROR_AUTH_PASSWORD` | Enables HTTP Basic Auth for the UI & management API (`/payloads.json` and `/api/health` always stay public) |
| `GIT_USERNAME` / `GIT_PASSWORD` | GitHub credentials (personal access token) for "Publish to GitHub" |
| `GIT_AUTHOR_NAME` / `GIT_AUTHOR_EMAIL` | Commit author for automatic pushes |

All four Git variables must be set for the "Publish to GitHub" workflow to work.

## Working with the mirror

**Via the web UI** (recommended): add a payload by GitHub release URL, pick the right file if a release contains multiple `.elf` files, adjust title/visibility/order, trigger a manual update, configure the update scheduler (default: every 4h, adjustable 1–24h).

**Via the CLI:**

```bash
# Interactively add a new payload
python add_payload.py

# Update all payloads (fetches new releases, updates README + payloads.json)
python update_payloads.py
```

The full API reference (routes, scheduler, Git endpoints) is in [WEBUI.md](WEBUI.md).

## Development with OpenSpec

New features and larger changes are developed using the **Spec-Driven Development** approach via [OpenSpec](openspec/) – no separate CLI tool required, the workflow runs directly through Claude Code skills/slash commands.

Typical flow:

```text
/opsx:explore   → think through the idea/problem, clarify requirements
/opsx:propose   → generate a change proposal including design & specs
/opsx:apply     → implement the tasks from the change
/opsx:sync      → merge delta specs into the main specs
/opsx:archive   → archive the completed change
```

- Current feature specs live under `openspec/specs/` (e.g. `git-publish`, `mirror-visibility`, `update-scheduler`, `mirror-editing`).
- Completed change proposals are archived under `openspec/changes/archive/`.
- Configuration lives in `openspec/config.yaml` (schema `spec-driven`).

## Automation (GitHub Actions)

The workflow [`.github/workflows/update_mirror.yml`](.github/workflows/update_mirror.yml) runs:

- every 2 hours (cron `0 */2 * * *`),
- on every push to `main`,
- manually via `workflow_dispatch`.

It calls `update_payloads.py`, uploads new assets as GitHub release files (`gh release upload --clobber`), and automatically commits and pushes changes to `payloads.json` and `README.md`.

## Available payloads

<!-- PAYLOADS_START -->
| Payload | Version | Description | Last Updated | Source | Download |
| --- | --- | --- | --- | --- | --- |
| **cheatrunner** | `v0.15` | CheatRunner is a PS5 web launcher and cheat trainer for already-jailbroken PS5 consoles. | `2026-07-07` | [Source](https://github.com/notmaj0r/CheatRunner/releases) | [Download](https://github.com/baschte/ps5-payloads-mirror/releases/download/payloads-mirror/cheatrunner_v0.15.elf) |
| **ps5-bar-tool-all** | `Release` | PS5 implements a feature called "Backup and Restore" (BAR) to allow users to move or save user data and application information. | `2026-06-29` | [Source](https://github.com/chibsaabji/ps5-bar-tool/releases) | [Download](https://github.com/baschte/ps5-payloads-mirror/releases/download/payloads-mirror/ps5-bar-tool-all_Release.elf) |
| **ps5-bar-tool-info** | `Release` | PS5 implements a feature called "Backup and Restore" (BAR) to allow users to move or save user data and application information. | `2026-06-29` | [Source](https://github.com/chibsaabji/ps5-bar-tool/releases) | [Download](https://github.com/baschte/ps5-payloads-mirror/releases/download/payloads-mirror/ps5-bar-tool-info_Release.elf) |
| **ps5-bar-tool-savedata** | `Release` | PS5 implements a feature called "Backup and Restore" (BAR) to allow users to move or save user data and application information. | `2026-06-29` | [Source](https://github.com/chibsaabji/ps5-bar-tool/releases) | [Download](https://github.com/baschte/ps5-payloads-mirror/releases/download/payloads-mirror/ps5-bar-tool-savedata_Release.elf) |
| **ps5-bar-tool-main-segment** | `Release` | PS5 implements a feature called "Backup and Restore" (BAR) to allow users to move or save user data and application information. | `2026-06-29` | [Source](https://github.com/chibsaabji/ps5-bar-tool/releases) | [Download](https://github.com/baschte/ps5-payloads-mirror/releases/download/payloads-mirror/ps5-bar-tool-main-segment_Release.elf) |
| **pegasus-dl** | `v1.7.0` | Direct package downloading from your PS5, managed through a local web interface. | `2026-06-24` | [Source](https://github.com/pegasus-ps5/pegasus-dl/releases) | [Download](https://github.com/baschte/ps5-payloads-mirror/releases/download/payloads-mirror/pegasus-dl_v1.7.0.elf) |
| **PS5-Game-Compressor** | `v1.0.3` | Standalone PS5 payload for compressing, unpacking, validating, repairing, and moving ShadowMountPlus-mounted games from a simple web UI. | `2026-06-20` | [Source](https://github.com/juma-sayeh/PS5-Game-Compressor/releases) | [Download](https://github.com/baschte/ps5-payloads-mirror/releases/download/payloads-mirror/PS5-Game-Compressor_v1.0.3.elf) |
| **ps5-app-dumper** | `v1.10` | A small utility to dump PS5 application files from the console's pfsmnt to a connected USB storage device. | `2026-05-03` | [Source](https://github.com/EchoStretch/ps5-app-dumper/releases) | [Download](https://github.com/baschte/ps5-payloads-mirror/releases/download/payloads-mirror/ps5-app-dumper_v1.10.elf) |
| **ps5upload** | `v4.0.0` | Fast, reliable transfers from your computer to your PS5. | `2026-07-11` | [Source](https://github.com/phantomptr/ps5upload/releases) | [Download](https://github.com/baschte/ps5-payloads-mirror/releases/download/payloads-mirror/ps5upload_v4.0.0.elf) |
| **garlic-savemgr** | `v1.12` | PS5 save decrypt/encrypt/browse with embedded web UI. | `2026-07-13` | [Source](https://git.etawen.dev/earthonion/garlic-savemgr/releases) | [Download](https://github.com/baschte/ps5-payloads-mirror/releases/download/payloads-mirror/garlic-savemgr_v1.12.elf) |
| **kstuff-lite** | `v1.09` | Lite version of kstuff | `2026-07-04` | [Source](https://github.com/EchoStretch/kstuff-lite/releases) | [Download](https://github.com/baschte/ps5-payloads-mirror/releases/download/payloads-mirror/kstuff-lite_v1.09.elf) |
| **shadowmountplus** | `1.6beta16` | A fully automated, background 'Auto-Mounter' payload for Jailbroken PlayStation 5 consoles. | `2026-06-28` | [Source](https://github.com/drakmor/ShadowMountPlus/releases) | [Download](https://github.com/baschte/ps5-payloads-mirror/releases/download/payloads-mirror/shadowmountplus_1.6beta16.elf) |
| **ps5debug-NG** | `1.3.0` | PS5 debugger payload - userland TCP wire-protocol server hosted inside SceShellCore. | `2026-06-21` | [Source](https://github.com/OpenSourcereR-dev/ps5debug-NG/releases) | [Download](https://github.com/baschte/ps5-payloads-mirror/releases/download/payloads-mirror/ps5debug-NG_1.3.0.elf) |
| **nanoDNS** | `0.3` | Minimal PS4/PS5 payload DNS proxy | `2026-06-03` | [Source](https://github.com/drakmor/nanoDNS/releases) | [Download](https://github.com/baschte/ps5-payloads-mirror/releases/download/payloads-mirror/nanoDNS_0.3.elf) |
| **klogsrv** | `v0.8` | A simple socket server that redirects /dev/klog to sockets connected on port 3232 | `2026-05-12` | [Source](https://github.com/ps5-payload-dev/klogsrv/releases) | [Download](https://github.com/baschte/ps5-payloads-mirror/releases/download/payloads-mirror/klogsrv_v0.8.elf) |
| **shsrv** | `v0.19` | A simple telnet-like shell server for jailbroken PS5s that accepts connections on port 2323 | `2026-06-28` | [Source](https://github.com/ps5-payload-dev/shsrv/releases) | [Download](https://github.com/baschte/ps5-payloads-mirror/releases/download/payloads-mirror/shsrv_v0.19.elf) |
<!-- PAYLOADS_END -->

## Support & Suggestions

If you have suggestions for a new payload to be added, or run into an issue with one, please report it in the [Issues section](https://github.com/itsPLK/ps5-payloads-mirror/issues/new).

## Credits & Thanks

This project is based on the original [ps5-payloads-mirror by itsPLK](https://github.com/itsPLK/ps5-payloads-mirror). A big thank you to itsPLK for the original idea and foundation of this mirror – and to all the payload developers in the PS5 homebrew community, without whom this mirror wouldn't exist. 🙏
