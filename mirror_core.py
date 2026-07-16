"""Core, non-interactive logic for the PS5 payloads mirror.

This module holds the reusable building blocks that were previously baked into
the interactive CLI scripts (``add_payload.py`` / ``update_payloads.py``).

Functions here never call ``input()`` and never ``sys.exit()``. They return
values and raise :class:`MirrorError` (or a subclass) on failure so they can be
driven from both the CLI wrappers and the FastAPI backend.

All paths are resolved relative to this file's directory so the logic works
regardless of the current working directory.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# Serializes read-modify-write operations on payloads.json so that a scheduled
# update and a manual one (or two API calls) can never clobber each other.
# Acquire it around any mutating operation at the call site.
DATA_LOCK = threading.Lock()

# Callbacks invoked after every successful write of payloads.json (any path:
# manual API edit, scheduled update, title change). The server registers one to
# trigger auto-publishing; the CLI/GitHub Action register none, so they stay
# decoupled. Hooks run under DATA_LOCK and must be non-blocking and cheap.
_POST_WRITE_HOOKS = []


def register_post_write_hook(fn):
    """Register ``fn()`` to be called after each successful payloads.json write."""
    _POST_WRITE_HOOKS.append(fn)

BASE_DIR = Path(__file__).resolve().parent
JSON_FILE = BASE_DIR / "payloads.json"
# Local-only storage for hidden mirrors. Never git-tracked, never committed or
# pushed by server/git_ops.py — see that module's COMMIT_FILES for why it must
# stay excluded.
HIDDEN_JSON_FILE = BASE_DIR / "hidden_payloads.json"
PAYLOADS_DIR = BASE_DIR / "payloads"
README_FILE = BASE_DIR / "README.md"
BASE_URL = "https://github.com/baschte/ps5-payloads-mirror/releases/download/payloads-mirror"

MIRROR_OWNER = "baschte"
MIRROR_REPO = "ps5-payloads-mirror"

# Fallback title used only when payloads.json has no name (e.g. a freshly
# migrated legacy file). A name already stored in the file always wins, so the
# UI/Action keep whatever was set. Configure once via the MIRROR_TITLE env var
# and you never have to re-enter it.
DEFAULT_TITLE = os.environ.get("MIRROR_TITLE") or "PS5 Payloads Mirror"

FIELD_ORDER = [
    "name", "filename", "url", "source", "source_direct",
    "asset_pattern", "extract_file", "description",
    "last_update", "version", "checksum", "sort_order", "hidden",
]


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class MirrorError(Exception):
    """Base error for mirror operations (maps to HTTP 400 by default)."""


class DuplicateError(MirrorError):
    """A payload from the given source already exists (HTTP 409)."""


class NotFoundError(MirrorError):
    """Requested payload does not exist (HTTP 404)."""


class ZipExtractNeeded(MirrorError):
    """A ZIP asset contains multiple .elf files; caller must pick one (HTTP 422).

    ``candidates`` lists the selectable internal paths.
    """

    def __init__(self, candidates):
        self.candidates = candidates
        super().__init__(
            "ZIP archive contains multiple .elf files; specify extract_file. "
            f"Candidates: {', '.join(candidates)}"
        )


class AmbiguousAssetError(MirrorError):
    """A release has more than one plausible asset/file; caller must pick one (HTTP 422).

    ``candidates`` is a flattened list of dicts, each shaped like::

        {"asset_name": "<top-level asset filename>", "member_name": "<in-zip path or None>",
         "label": "<human-readable choice>"}

    One entry per plausible top-level asset, plus one entry per plausible
    .elf/.bin member for every top-level asset that is a ZIP.
    """

    def __init__(self, candidates):
        self.candidates = candidates
        labels = ", ".join(c["label"] for c in candidates)
        super().__init__(
            f"Release has multiple candidate files; specify which one to use. "
            f"Candidates: {labels}"
        )


# --------------------------------------------------------------------------- #
# Generic helpers (ported verbatim in behaviour from the original scripts)
# --------------------------------------------------------------------------- #
def get_repo_info(url):
    """Extract (domain, owner, repo) from a Git release URL."""
    match = re.search(r"https?://([^/]+)/([^/]+)/([^/]+)", url)
    if match:
        domain = match.group(1)
        owner = match.group(2)
        repo = match.group(3).rstrip("/")
        if repo.endswith(".git"):
            repo = repo[:-4]
        if repo == "releases":
            parts = url.split("/")
            try:
                idx = parts.index(domain)
                owner = parts[idx + 1]
                repo = parts[idx + 2]
            except (ValueError, IndexError):
                pass
        return domain, owner, repo
    return None, None, None


def _newest_release(releases):
    """Pick the newest non-draft release from a /releases listing.

    The listing is newest-first, so the first non-draft wins — this includes
    pre-releases, so repos that only publish pre-releases still resolve.
    """
    for rel in releases:
        if not rel.get("draft"):
            return rel
    return None


def get_latest_release(domain, owner, repo):
    """Fetch the latest release JSON for github.com (via gh) or a Gitea host.

    Prefers the stable "latest" release; if there is none (e.g. the repo only
    publishes pre-releases), falls back to the newest non-draft release.
    """
    try:
        if domain == "github.com":
            latest = subprocess.run(
                ["gh", "api", f"repos/{owner}/{repo}/releases/latest"],
                capture_output=True, text=True,
            )
            if latest.returncode == 0:
                return json.loads(latest.stdout)
            # No stable release → fall back to the newest non-draft (incl. pre-release).
            listing = subprocess.run(
                ["gh", "api", f"repos/{owner}/{repo}/releases"],
                capture_output=True, text=True,
            )
            if listing.returncode == 0:
                return _newest_release(json.loads(listing.stdout))
            return None

        def _get(path):
            url = f"https://{domain}/api/v1/repos/{owner}/{repo}/{path}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode("utf-8"))

        try:
            return _get("releases/latest")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            return _newest_release(_get("releases"))
    except Exception as e:
        print(f"Error fetching {domain}/{owner}/{repo}: {e}")
        return None


def download_file(url, filename):
    """Download ``url`` into ``PAYLOADS_DIR/filename``. Returns True on success."""
    PAYLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = PAYLOADS_DIR / filename
    print(f"  Downloading {filename}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response, open(filepath, "wb") as f:
            f.write(response.read())
        return True
    except Exception as e:
        print(f"  Error downloading {filename}: {e}")
        return False


def calculate_checksum(filepath):
    """SHA256 of a file, or None on error."""
    sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        print(f"  Error calculating checksum: {e}")
        return None


def reorder_item(item):
    """Return ``item`` with keys in canonical order."""
    new_item = {key: item[key] for key in FIELD_ORDER if key in item}
    for key in item:
        if key not in new_item:
            new_item[key] = item[key]
    return new_item


# --------------------------------------------------------------------------- #
# JSON persistence
#
# payloads.json shape: {"name": "<collection title>", "payloads": [ ... ]}.
# Older files were a bare list; load_data() transparently migrates them, and the
# next save writes the wrapped form.
#
# hidden_payloads.json holds the same shape, but its "name" is unused — it
# exists purely as a container for hidden items' "payloads" list, is never
# git-tracked, and must never be added to server/git_ops.py's COMMIT_FILES.
#
# Ordering is driven entirely by each item's "sort_order" (an int); items
# missing one (pre-existing data from before this field existed) are backfilled
# based on their current position the first time they're loaded.
# --------------------------------------------------------------------------- #
def _read_json_document(path):
    """Return ``(name, payloads)`` from a payloads-shaped JSON file, or
    ``(None, [])`` if the file is missing. Tolerates the legacy bare-list form."""
    try:
        with open(path, "r") as f:
            raw = json.load(f)
    except FileNotFoundError:
        return None, []

    if isinstance(raw, list):  # legacy bare-list form
        return None, raw
    if isinstance(raw, dict):
        return raw.get("name"), (raw.get("payloads") or [])
    return None, []


def _backfill_sort_order(payloads):
    """Assign a ``sort_order`` to any item missing one, based on its current
    position, so pre-existing data keeps its prior visual order as the
    baseline instead of being scrambled by the introduction of this field."""
    next_order = max((p["sort_order"] for p in payloads if "sort_order" in p), default=-1) + 1
    for item in payloads:
        if "sort_order" not in item:
            item["sort_order"] = next_order
            next_order += 1


def load_data():
    """Return the merged document as ``{"name": str, "payloads": list}``.

    ``payloads`` combines the visible file (``payloads.json``) and the hidden
    file (``hidden_payloads.json``, if present), each item tagged with
    ``hidden`` (``False``/``True`` respectively unless already set), sorted by
    ``sort_order`` (backfilled for any item missing one).
    """
    visible_name, visible = _read_json_document(JSON_FILE)
    _, hidden = _read_json_document(HIDDEN_JSON_FILE)

    for item in visible:
        item.setdefault("hidden", False)
    for item in hidden:
        item["hidden"] = True

    payloads = visible + hidden
    _backfill_sort_order(payloads)
    payloads.sort(key=lambda x: x["sort_order"])

    return {"name": (visible_name or DEFAULT_TITLE), "payloads": payloads}


def load_payloads():
    """Load the merged payload list (empty if both files are missing)."""
    return load_data()["payloads"]


def get_title():
    """The collection title shown in the UI / README / feed."""
    return load_data()["name"]


def _write_json_document(path, name, payloads):
    """Atomically persist ``{"name": name, "payloads": payloads}`` to ``path``.

    Prefers an atomic write (temp file + ``os.replace``) so a concurrent reader
    never sees a half-written file. When the target is a Docker bind-mounted
    *file*, renaming onto it fails (``EBUSY``/``EXDEV`` — it's a mount point), so
    we fall back to an in-place write.
    """
    data = json.dumps({"name": name, "payloads": payloads}, indent=2)

    fd, tmp_path = tempfile.mkstemp(dir=str(BASE_DIR), suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(data)
        try:
            os.replace(tmp_path, path)
        except OSError:
            # Bind-mounted file: can't rename onto a mount point — write in place.
            with open(path, "w") as f:
                f.write(data)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _write_data(name, payloads):
    """Sort, reorder, split by ``hidden`` and persist both documents, then
    regenerate the README from the visible subset. Writers are serialized by
    ``DATA_LOCK``.
    """
    payloads.sort(key=lambda x: x.get("sort_order", 0))
    payloads = [reorder_item(p) for p in payloads]

    visible = [p for p in payloads if not p.get("hidden")]
    hidden = [p for p in payloads if p.get("hidden")]

    _write_json_document(JSON_FILE, name, visible)
    _write_json_document(HIDDEN_JSON_FILE, name, hidden)

    update_readme()
    for hook in _POST_WRITE_HOOKS:
        try:
            hook()
        except Exception:
            # A misbehaving hook must never break persistence.
            pass
    return payloads


def save_payloads(payloads):
    """Persist the payload list, preserving the current collection title."""
    return _write_data(get_title(), payloads)


def set_title(name):
    """Set the collection title; returns the stored (trimmed) value."""
    name = (name or "").strip() or DEFAULT_TITLE
    _write_data(name, load_data()["payloads"])
    return name


# --------------------------------------------------------------------------- #
# README generation
# --------------------------------------------------------------------------- #
def update_readme():
    """Regenerate the payload table inside README.md from payloads.json.

    Only visible mirrors are included — hidden ones are excluded from the
    published README, matching the public payloads.json feed.
    """
    data = load_data()
    title = data["name"]
    payloads = [p for p in data["payloads"] if not p.get("hidden")]

    table_rows = [
        "| Payload | Version | Description | Last Updated | Source | Download |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in payloads:
        name = item.get("name", "Unknown")
        version = item.get("version", "Unknown")
        description = item.get("description") or "No description provided."
        last_update = item.get("last_update", "Unknown")
        source = item.get("source", "#")
        url = item.get("url", "#")
        table_rows.append(
            f"| **{name}** | `{version}` | {description} | `{last_update}` | "
            f"[Source]({source}) | [Download]({url}) |"
        )
    table_content = "\n".join(table_rows)

    template = f"""# {title}

This repository contains an automated mirror of useful payloads for the PlayStation 5.

## Available Payloads

<!-- PAYLOADS_START -->
{table_content}
<!-- PAYLOADS_END -->

## Support & Suggestions

If you have suggestions for a new payload to be added or if there's an important issue with some payload, please report them in the [Issues section](https://github.com/baschte/ps5-payloads-mirror/issues/new).
"""

    start_marker = "<!-- PAYLOADS_START -->"
    end_marker = "<!-- PAYLOADS_END -->"

    if not README_FILE.exists():
        print(f"Creating {README_FILE.name}...")
        README_FILE.write_text(template)
        return

    print(f"Updating {README_FILE.name}...")
    content = README_FILE.read_text()
    if start_marker in content and end_marker in content:
        pattern = re.compile(f"{start_marker}.*?{end_marker}", re.DOTALL)
        new_content = pattern.sub(
            f"{start_marker}\n{table_content}\n{end_marker}", content
        )
        README_FILE.write_text(new_content)
    else:
        print("Markers not found in README.md. Appending table at the end.")
        with open(README_FILE, "a") as f:
            f.write(
                f"\n## Available Payloads\n\n{start_marker}\n"
                f"{table_content}\n{end_marker}\n"
            )


# --------------------------------------------------------------------------- #
# Mirror release assets
# --------------------------------------------------------------------------- #
def get_mirror_assets():
    """Names of assets currently attached to the published mirror release."""
    try:
        cmd = ["gh", "api", f"repos/{MIRROR_OWNER}/{MIRROR_REPO}/releases/tags/payloads-mirror"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            release_info = json.loads(result.stdout)
            return {asset["name"] for asset in release_info.get("assets", [])}
    except Exception as e:
        print(f"Error fetching mirror assets: {e}")
    return set()


def cleanup_release_assets():
    """Delete published release assets that no longer appear in payloads.json."""
    print("\nChecking for stale release assets to clean up...")
    try:
        payloads = load_payloads()
        expected_files = {p["filename"] for p in payloads if "filename" in p}

        cmd = ["gh", "api", f"repos/{MIRROR_OWNER}/{MIRROR_REPO}/releases/tags/payloads-mirror"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        release_info = json.loads(result.stdout)

        deleted_count = 0
        for asset in release_info.get("assets", []):
            if asset["name"] not in expected_files:
                print(f"  Removing stale asset: {asset['name']} (ID: {asset['id']})...")
                del_cmd = [
                    "gh", "api", "-X", "DELETE",
                    f"repos/{MIRROR_OWNER}/{MIRROR_REPO}/releases/assets/{asset['id']}",
                ]
                subprocess.run(del_cmd, check=True)
                print(f"  Successfully removed {asset['name']}.")
                deleted_count += 1

        print("  No stale assets to remove." if deleted_count == 0
              else f"  Removed {deleted_count} stale assets.")
    except Exception as e:
        print(f"Error cleaning up release assets: {e}")


# --------------------------------------------------------------------------- #
# Asset selection
# --------------------------------------------------------------------------- #
def _extract_zip_member(gh_url, filename, extract_file):
    """Download a ZIP from ``gh_url`` and extract one .elf member to PAYLOADS_DIR.

    Returns the chosen ``extract_file``. Raises :class:`ZipExtractNeeded` when
    the member is ambiguous, or :class:`MirrorError` on other failures.
    """
    PAYLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = PAYLOADS_DIR / filename
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_path = tmp_file.name
    try:
        req = urllib.request.Request(gh_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response, open(tmp_path, "wb") as f:
            f.write(response.read())

        with zipfile.ZipFile(tmp_path, "r") as z:
            elf_files = [n for n in z.namelist() if n.lower().endswith(".elf")]
            if not extract_file:
                if len(elf_files) == 1:
                    extract_file = elf_files[0]
                elif len(elf_files) > 1:
                    raise ZipExtractNeeded(elf_files)
                else:
                    raise MirrorError("No .elf files found in zip.")
            elif extract_file not in z.namelist():
                raise MirrorError(f"{extract_file} not found in zip.")

            with z.open(extract_file) as src, open(filepath, "wb") as dst:
                shutil.copyfileobj(src, dst)
        return extract_file
    except (ZipExtractNeeded, MirrorError):
        raise
    except Exception as e:
        raise MirrorError(f"Error processing zip: {e}") from e
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _list_zip_members(gh_url):
    """Download the ZIP at ``gh_url`` and return its plausible .elf/.bin member names."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_path = tmp_file.name
    try:
        req = urllib.request.Request(gh_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response, open(tmp_path, "wb") as f:
            f.write(response.read())
        with zipfile.ZipFile(tmp_path, "r") as z:
            return [n for n in z.namelist() if n.lower().endswith((".elf", ".bin"))]
    except (OSError, zipfile.BadZipFile) as e:
        raise MirrorError(f"Error processing zip: {e}") from e
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def list_candidates(assets):
    """Build the flattened candidate list for a release's assets.

    One entry per plausible top-level asset (.elf/.bin/.zip), plus — for any
    top-level asset that is a .zip — one entry per plausible .elf/.bin member
    inside it. ZIP contents are only probed when the ZIP is itself a
    plausible top-level candidate alongside others (i.e. we still skip
    probing when a non-ZIP asset already makes the release unambiguous),
    mirroring add_payload's historical elf/bin-over-zip preference.

    Returns a list of dicts: {"asset_name", "member_name", "label"}.
    """
    plausible = [a for a in assets if a["name"].lower().endswith((".elf", ".bin", ".zip"))]
    non_zip = [a for a in plausible if not a["name"].lower().endswith(".zip")]
    zips = [a for a in plausible if a["name"].lower().endswith(".zip")]

    # Fast path: a single non-zip asset and nothing else plausible — no need
    # to probe any zip contents at all.
    if len(non_zip) == 1 and not zips:
        a = non_zip[0]
        return [{"asset_name": a["name"], "member_name": None, "label": a["name"]}]
    if len(plausible) == 1:
        a = plausible[0]
        if a["name"].lower().endswith(".zip"):
            members = _list_zip_members(a["browser_download_url"])
            if len(members) == 1:
                return [{
                    "asset_name": a["name"], "member_name": members[0],
                    "label": f"{a['name']} → {members[0]}",
                }]
            return [
                {"asset_name": a["name"], "member_name": m, "label": f"{a['name']} → {m}"}
                for m in members
            ]
        return [{"asset_name": a["name"], "member_name": None, "label": a["name"]}]

    candidates = []
    for a in non_zip:
        candidates.append({"asset_name": a["name"], "member_name": None, "label": a["name"]})
    for a in zips:
        members = _list_zip_members(a["browser_download_url"])
        for m in members:
            candidates.append({
                "asset_name": a["name"], "member_name": m, "label": f"{a['name']} → {m}",
            })
    return candidates


def resolve_candidate(assets, asset_name=None, member_name=None):
    """Resolve a release's assets down to exactly one candidate.

    If ``asset_name`` (and, for a ZIP, ``member_name``) is given, that exact
    candidate is used (after validating it still exists). Otherwise, builds
    the flattened list via :func:`list_candidates`: exactly one candidate is
    auto-selected, more than one raises :class:`AmbiguousAssetError`.

    Returns a dict: {"asset": <asset dict>, "member_name": str | None}.
    """
    if asset_name:
        asset = next((a for a in assets if a["name"] == asset_name), None)
        if not asset:
            raise MirrorError(f"Asset {asset_name!r} not found in the latest release.")
        if asset["name"].lower().endswith(".zip"):
            members = _list_zip_members(asset["browser_download_url"])
            if member_name:
                if member_name not in members:
                    raise MirrorError(f"{member_name!r} not found in {asset_name!r}.")
                return {"asset": asset, "member_name": member_name}
            if len(members) == 1:
                return {"asset": asset, "member_name": members[0]}
            raise AmbiguousAssetError([
                {"asset_name": asset["name"], "member_name": m, "label": f"{asset['name']} → {m}"}
                for m in members
            ])
        return {"asset": asset, "member_name": None}

    candidates = list_candidates(assets)
    if not candidates:
        raise MirrorError("Could not find a suitable .elf, .bin or .zip asset in the latest release.")
    if len(candidates) > 1:
        raise AmbiguousAssetError(candidates)
    chosen = candidates[0]
    asset = next(a for a in assets if a["name"] == chosen["asset_name"])
    return {"asset": asset, "member_name": chosen["member_name"]}


def select_update_asset(assets, item):
    """Resolve the asset to use for an automatic update of an *existing* payload.

    Deterministic: filters strictly by the item's stored ``asset_pattern``
    (exact top-level asset filename) and, for a ZIP, its stored
    ``extract_file`` member — no scoring, no prompting. Returns
    ``{"asset": dict, "member_name": str | None}`` or ``None`` if the stored
    candidate can no longer be found.

    For legacy items with no stored ``asset_pattern`` (created before this
    function existed), falls back to the original scoring heuristic exactly
    once so a candidate can still be picked and then persisted going forward
    by the caller.
    """
    asset_pattern = item.get("asset_pattern")
    if asset_pattern:
        asset = next((a for a in assets if a["name"] == asset_pattern), None)
        if not asset:
            return None
        member_name = item.get("extract_file")
        if asset["name"].lower().endswith(".zip") and member_name:
            members = _list_zip_members(asset["browser_download_url"])
            if member_name not in members:
                return None
        return {"asset": asset, "member_name": member_name}

    return _legacy_score_asset(assets, item)


def _legacy_score_asset(assets, item):
    """Original scoring heuristic, kept only as a one-time fallback for
    payloads that predate stored asset_pattern/extract_file selections."""
    repo_name = item.get("name", "")
    has_extract = "extract_file" in item
    preferred_ext = ".bin" if "etaHEN" in repo_name else ".elf"

    def score_asset(name):
        name_lower = name.lower()
        if has_extract and name.endswith(".zip"):
            return 20
        if not (name.endswith(".elf") or name.endswith(".bin")
                or (has_extract and name.endswith(".zip"))):
            if not name.endswith(preferred_ext):
                return -1
        score = 0
        if name.endswith(preferred_ext):
            score += 5
        if "ps5" in name_lower:
            score += 10
        if "ps4" in name_lower:
            score -= 10
        if "install" in name_lower:
            score -= 5
        score -= len(name) / 100.0
        return score

    selected, best = None, -2
    for asset in assets:
        s = score_asset(asset["name"])
        if s > best:
            best, selected = s, asset
    if not (selected and best > -1):
        return None

    member_name = None
    if selected["name"].lower().endswith(".zip"):
        member_name = item.get("extract_file")
        if not member_name:
            members = _list_zip_members(selected["browser_download_url"])
            member_name = members[0] if len(members) == 1 else None
    return {"asset": selected, "member_name": member_name}


# --------------------------------------------------------------------------- #
# Public operations
# --------------------------------------------------------------------------- #
def _slugify(title):
    """Derive a mirror ``name`` from a ``title``: lowercase, collapse every
    run of non-alphanumeric characters to a single ``-``, strip leading and
    trailing ``-``. E.g. ``"PS5 Bar Tool - All"`` -> ``"ps5-bar-tool-all"``.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", title.strip().lower())
    return slug.strip("-")


def _find_duplicate_candidate(payloads, source_url, asset_name, member_name):
    """Find an existing payload mirroring the same source AND the same
    resolved candidate (asset name + extracted member, if any). Different
    assets/files from the same source are not duplicates of each other."""
    return next(
        (p for p in payloads
         if p.get("source") == source_url
         and p.get("asset_pattern") == asset_name
         and p.get("extract_file") == member_name),
        None,
    )


def _duplicate_candidate_message(source_url, asset_name, member_name):
    suffix = f" ({member_name})" if member_name else ""
    return f"A payload from {source_url} using {asset_name}{suffix} already exists."


def _resolve_release_and_asset(url, asset_name=None, extract_file=None):
    """Shared resolution used by both add_payload and edit_payload.

    Parses ``url`` into (domain, owner, repo), fetches the latest release,
    and resolves exactly one candidate asset/member — either the caller's
    explicit ``asset_name``/``extract_file`` choice, or (if the URL itself
    points at a specific asset filename and no explicit choice was made)
    that exact filename, or via the flattened candidate list.

    Returns ``(domain, owner, repo, release, asset, member_name)``.
    Raises :class:`MirrorError` / :class:`AmbiguousAssetError`.
    """
    domain, owner, repo = get_repo_info(url)
    if not owner:
        raise MirrorError("Could not parse Git domain/owner/repo from URL.")

    release = get_latest_release(domain, owner, repo)
    if not release:
        raise MirrorError(f"Could not fetch latest release for {owner}/{repo} on {domain}.")

    assets = release.get("assets", [])

    if not asset_name:
        filename_match = re.search(r"/([^/]+\.(elf|bin|zip))$", url)
        if filename_match and any(a["name"] == filename_match.group(1) for a in assets):
            asset_name = filename_match.group(1)

    resolved = resolve_candidate(assets, asset_name=asset_name, member_name=extract_file)
    return domain, owner, repo, release, resolved["asset"], resolved["member_name"]


def add_payload(url, description="", extract_file=None, asset_name=None, title=None):
    """Add a new mirror from a release ``url``. Returns the new payload dict.

    ``asset_name``/``extract_file`` pin an explicit candidate (as returned by
    a prior :class:`AmbiguousAssetError`); otherwise the release's assets are
    resolved via the flattened candidate list, auto-selecting when there's
    exactly one plausible candidate.

    ``title``, if given, is stored as the mirror's display title, and its
    slug (see :func:`_slugify`) is used as ``name`` instead of the repo name.

    Raises :class:`MirrorError` / :class:`DuplicateError` / :class:`AmbiguousAssetError`.
    """
    url = (url or "").strip()
    if not url:
        raise MirrorError("URL is required.")

    domain, owner, repo, release, selected_asset, member_name = _resolve_release_and_asset(
        url, asset_name=asset_name, extract_file=extract_file
    )

    payloads = load_payloads()
    source_url = f"https://{domain}/{owner}/{repo}/releases"
    if _find_duplicate_candidate(payloads, source_url, selected_asset["name"], member_name):
        raise DuplicateError(
            _duplicate_candidate_message(source_url, selected_asset["name"], member_name)
        )

    item_name = repo
    if title and title.strip():
        slug = _slugify(title)
        if slug:
            if any(p.get("name") == slug for p in payloads):
                raise DuplicateError(f"A payload named {slug!r} already exists.")
            item_name = slug

    new_item = _download_and_build_item(
        item_name, source_url, release, selected_asset, member_name, description, title=title
    )
    new_item["sort_order"] = max(
        (p.get("sort_order", -1) for p in payloads), default=-1
    ) + 1
    new_item["hidden"] = False

    payloads.append(new_item)
    save_payloads(payloads)
    return reorder_item(new_item)


def _download_and_build_item(name, source_url, release, selected_asset, member_name, description, title=None):
    """Download the resolved asset (extracting ``member_name`` if it's a ZIP)
    and build the payload dict. Shared by add_payload and edit_payload."""
    gh_url = selected_asset["browser_download_url"]
    new_version = release["tag_name"]
    is_zip = selected_asset["name"].lower().endswith(".zip")
    if is_zip:
        ext = "elf"
    else:
        ext = (selected_asset["name"].rsplit(".", 1)[1]
               if "." in selected_asset["name"] else "bin")

    filename = f"{name}_{new_version}.{ext}"
    filepath = PAYLOADS_DIR / filename

    if is_zip:
        _extract_zip_member(gh_url, filename, member_name)
    else:
        if not download_file(gh_url, filename):
            raise MirrorError("Failed to download the payload asset.")

    new_item = {
        "name": name,
        "filename": filename,
        "title": (title or "").strip() or None,
        "url": f"{BASE_URL}/{filename}",
        "source": source_url,
        "source_direct": gh_url,
        "asset_pattern": selected_asset["name"],
        "description": (description or "").strip(),
        "last_update": release["published_at"][:10],
        "version": new_version,
        "checksum": calculate_checksum(filepath),
    }
    if is_zip and member_name:
        new_item["extract_file"] = member_name
    return new_item


def list_candidates_for_payload(name):
    """Read-only: fetch the latest release for an existing mirror's current
    source and return its flattened candidate list (see list_candidates),
    without persisting anything. Used by the edit UI to let the user switch
    assets/files even when the source URL itself isn't changing.

    Returns a list of dicts: {"asset_name", "member_name", "label"}.
    Raises :class:`NotFoundError` / :class:`MirrorError`.
    """
    payloads = load_payloads()
    item = next((p for p in payloads if p.get("name") == name), None)
    if item is None:
        raise NotFoundError(f"No payload named {name!r}.")

    source = item.get("source")
    if not source:
        raise MirrorError("This mirror has no source URL to resolve.")

    domain, owner, repo = get_repo_info(source)
    if not owner:
        raise MirrorError("Could not parse Git domain/owner/repo from source URL.")

    release = get_latest_release(domain, owner, repo)
    if not release:
        raise MirrorError(f"Could not fetch latest release for {owner}/{repo} on {domain}.")

    assets = release.get("assets", [])
    candidates = list_candidates(assets)
    if not candidates:
        raise MirrorError("Could not find a suitable .elf, .bin or .zip asset in the latest release.")
    return candidates


def edit_payload(name, url=None, description=None, extract_file=None, asset_name=None, title=None):
    """Edit an existing mirror in place. Returns the updated payload dict.

    - If ``url`` is omitted, the mirror's source is left unchanged.
      ``description`` and ``title`` are always patched with no network call.
      When ``title`` is set and its slug (see :func:`_slugify`) differs from
      the mirror's current ``name``, the mirror is renamed: its ``name``,
      ``filename`` (renamed on disk, not re-downloaded) and ``url`` are
      updated to match, rejected if the slug collides with a *different*
      mirror's ``name``. If ``asset_name`` and/or ``extract_file`` name a
      different candidate than currently stored, the source's latest release
      is re-fetched and that candidate is downloaded/extracted, without
      changing the source itself.
    - If ``url`` is given, the release is re-resolved exactly like
      add_payload (using ``asset_name``/``extract_file`` as an explicit pick
      when given), and the item is replaced in place at its current
      position — its name, filename, url, source, etc. may all change.
    - The duplicate-source check excludes the item being edited itself.

    Raises :class:`MirrorError` / :class:`DuplicateError` /
    :class:`NotFoundError` / :class:`AmbiguousAssetError`.
    """
    payloads = load_payloads()
    index = next((i for i, p in enumerate(payloads) if p.get("name") == name), None)
    if index is None:
        raise NotFoundError(f"No payload named {name!r}.")
    item = payloads[index]

    url = url.strip() if url else None
    source_unchanged = not url or url == item.get("source")

    if source_unchanged:
        # dict(item) copies sort_order/hidden along with everything else; the
        # asset-switch sub-branch below only updates via `rebuilt`, which never
        # carries those keys, so they're preserved without any extra handling.
        updated = dict(item)
        if description is not None:
            updated["description"] = description.strip()

        others = payloads[:index] + payloads[index + 1:]
        new_slug = None
        if title is not None:
            updated["title"] = title.strip() or None
            if updated["title"]:
                slug = _slugify(updated["title"])
                if slug and slug != item.get("name"):
                    if any(p.get("name") == slug for p in others):
                        raise DuplicateError(f"A payload named {slug!r} already exists.")
                    new_slug = slug

        asset_changed = asset_name is not None and asset_name != item.get("asset_pattern")
        member_changed = extract_file is not None and extract_file != item.get("extract_file")
        if asset_changed or member_changed:
            domain, owner, repo = get_repo_info(item["source"])
            release = get_latest_release(domain, owner, repo)
            if not release:
                raise MirrorError(f"Could not fetch latest release for {owner}/{repo} on {domain}.")
            resolved = resolve_candidate(
                release.get("assets", []),
                asset_name=asset_name or item.get("asset_pattern"),
                member_name=extract_file,
            )
            rebuilt = _download_and_build_item(
                new_slug or updated.get("name", name), updated["source"], release,
                resolved["asset"], resolved["member_name"], updated.get("description", ""),
                title=updated.get("title"),
            )
            if item.get("filename") and item["filename"] != rebuilt["filename"]:
                old_path = PAYLOADS_DIR / item["filename"]
                if old_path.exists():
                    old_path.unlink()
            updated.pop("extract_file", None)
            updated.update(rebuilt)
        elif new_slug:
            # Title-only change that renames the entry: move the existing
            # file on disk to match the new name, no re-download needed.
            old_filename = item.get("filename")
            new_filename = old_filename.replace(item["name"], new_slug, 1) if old_filename else old_filename
            if old_filename and new_filename != old_filename:
                old_path = PAYLOADS_DIR / old_filename
                new_path = PAYLOADS_DIR / new_filename
                if old_path.exists():
                    old_path.rename(new_path)
                updated["filename"] = new_filename
                updated["url"] = f"{BASE_URL}/{new_filename}"
            updated["name"] = new_slug

        payloads[index] = updated
        save_payloads(payloads)
        return reorder_item(updated)

    # Source URL changed: re-resolve fully, like add_payload, then replace in place.
    others = payloads[:index] + payloads[index + 1:]
    domain, owner, repo, release, selected_asset, member_name = _resolve_release_and_asset(
        url, asset_name=asset_name, extract_file=extract_file
    )
    source_url = f"https://{domain}/{owner}/{repo}/releases"
    if _find_duplicate_candidate(others, source_url, selected_asset["name"], member_name):
        raise DuplicateError(
            _duplicate_candidate_message(source_url, selected_asset["name"], member_name)
        )

    new_description = description if description is not None else item.get("description", "")
    new_title = title if title is not None else item.get("title")
    new_name = repo
    if new_title and new_title.strip():
        slug = _slugify(new_title)
        if slug:
            if any(p.get("name") == slug for p in others):
                raise DuplicateError(f"A payload named {slug!r} already exists.")
            new_name = slug
    new_item = _download_and_build_item(
        new_name, source_url, release, selected_asset, member_name, new_description, title=new_title
    )
    # Preserve manual sort order and hidden status across a source URL change —
    # neither is a side effect a URL edit should reset (see mirror-editing spec).
    new_item["sort_order"] = item.get("sort_order", 0)
    new_item["hidden"] = item.get("hidden", False)

    if item.get("filename") and item["filename"] != new_item["filename"]:
        old_path = PAYLOADS_DIR / item["filename"]
        if old_path.exists():
            old_path.unlink()

    payloads[index] = new_item
    save_payloads(payloads)
    return reorder_item(new_item)


def update_one(name, payloads=None, mirror_assets=None, persist=True):
    """Check a single payload for a newer release and download it if needed.

    Returns ``{"updated": bool, "item": dict, "message": str}``.
    """
    own_list = payloads is None
    if own_list:
        payloads = load_payloads()
    if mirror_assets is None:
        mirror_assets = get_mirror_assets()

    item = next((p for p in payloads if p.get("name") == name), None)
    if item is None:
        raise NotFoundError(f"No payload named {name!r}.")

    source = item.get("source")
    if not source:
        return {"updated": False, "item": reorder_item(item), "message": "No source to check."}

    domain, owner, repo_name = get_repo_info(source)
    if not owner:
        return {"updated": False, "item": reorder_item(item), "message": "Could not parse source URL."}

    release = get_latest_release(domain, owner, repo_name)
    if not release or not release.get("assets"):
        return {"updated": False, "item": reorder_item(item), "message": "No release/assets found upstream."}

    resolved = select_update_asset(release["assets"], item)
    if not resolved:
        return {"updated": False, "item": reorder_item(item),
                "message": "Previously selected asset no longer found upstream."}
    selected_asset = resolved["asset"]
    resolved_member_name = resolved["member_name"]

    gh_url = selected_asset["browser_download_url"]
    original_filename = selected_asset["name"]
    new_version = release["tag_name"]
    new_date = release["published_at"][:10]
    is_zip = original_filename.endswith(".zip")

    final_name = item.get("name", repo_name)
    if is_zip:
        ext = "elf"
    else:
        ext = original_filename.rsplit(".", 1)[1] if "." in original_filename else "bin"
    new_filename = f"{final_name}_{new_version}.{ext}"
    filepath = PAYLOADS_DIR / new_filename

    # Migration-on-touch: persist the resolved candidate identity so future
    # checks are deterministic (skip select_update_asset's legacy scoring
    # fallback entirely once this is recorded).
    candidate_changed = (
        item.get("asset_pattern") != selected_asset["name"]
        or (is_zip and item.get("extract_file") != resolved_member_name)
    )
    if candidate_changed:
        item["asset_pattern"] = selected_asset["name"]
        if is_zip and resolved_member_name:
            item["extract_file"] = resolved_member_name
        elif not is_zip:
            item.pop("extract_file", None)

    needs_download = (
        item.get("version") != new_version
        or item.get("filename") != new_filename
        or new_filename not in mirror_assets
    )
    if not needs_download:
        if candidate_changed and own_list and persist:
            save_payloads(payloads)
        return {"updated": False, "item": reorder_item(item),
                "message": f"Already up to date ({new_version})."}

    # Remove the now-outdated local file.
    if item.get("filename") and item["filename"] != new_filename:
        old_path = PAYLOADS_DIR / item["filename"]
        if old_path.exists():
            old_path.unlink()

    extract_file = resolved_member_name
    if is_zip:
        extract_file = _extract_zip_member(gh_url, new_filename, extract_file)
    else:
        if not download_file(gh_url, new_filename):
            return {"updated": False, "item": reorder_item(item),
                    "message": "Download failed; update skipped."}
        item.pop("extract_file", None)

    item["name"] = final_name
    item["version"] = new_version
    item["filename"] = new_filename
    item["url"] = f"{BASE_URL}/{new_filename}"
    item["source_direct"] = gh_url
    item["last_update"] = new_date
    item["checksum"] = calculate_checksum(filepath)
    item["asset_pattern"] = selected_asset["name"]
    if extract_file and is_zip:
        item["extract_file"] = extract_file

    if own_list and persist:
        save_payloads(payloads)
    return {"updated": True, "item": reorder_item(item),
            "message": f"Updated to {new_version}."}


def update_all(cleanup=False):
    """Check every payload for updates. Returns a list of per-payload results."""
    payloads = load_payloads()
    mirror_assets = get_mirror_assets()
    results = []
    for item in list(payloads):
        name = item.get("name")
        try:
            res = update_one(name, payloads=payloads, mirror_assets=mirror_assets)
        except MirrorError as e:
            res = {"updated": False, "item": reorder_item(item), "message": str(e)}
        results.append({"name": name, **res})

    # Refresh URLs to keep them in sync with filenames (as the original did).
    for item in payloads:
        if item.get("filename"):
            item["url"] = f"{BASE_URL}/{item['filename']}"

    save_payloads(payloads)
    if cleanup:
        cleanup_release_assets()
    return results


def remove_payload(name):
    """Remove a payload from the JSON and delete its local file (local only)."""
    payloads = load_payloads()
    item = next((p for p in payloads if p.get("name") == name), None)
    if item is None:
        raise NotFoundError(f"No payload named {name!r}.")

    filename = item.get("filename")
    if filename:
        path = PAYLOADS_DIR / filename
        if path.exists():
            print(f"Removing local file {filename}...")
            path.unlink()

    payloads = [p for p in payloads if p.get("name") != name]
    save_payloads(payloads)
    return {"removed": name}


def reorder_payloads(names_in_order):
    """Persist a new manual ordering for every known mirror (visible + hidden).

    ``names_in_order`` must contain exactly the current set of mirror names,
    each exactly once, in the desired order. Assigns sort_order in step
    increments and persists in one write. Returns the updated merged list.

    Raises :class:`MirrorError` if the given names don't exactly match the
    current set of known mirrors.
    """
    payloads = load_payloads()
    current_names = {p.get("name") for p in payloads}
    given_names = list(names_in_order)

    if len(given_names) != len(set(given_names)):
        raise MirrorError("Reorder list contains duplicate names.")
    if set(given_names) != current_names:
        raise MirrorError(
            "Reorder list must contain exactly the current set of mirror names."
        )

    order_index = {name: i for i, name in enumerate(given_names)}
    for item in payloads:
        item["sort_order"] = (order_index[item.get("name")] + 1) * 10

    save_payloads(payloads)
    return load_payloads()


def set_hidden(name, hidden):
    """Set a mirror's hidden status (moves it between payloads.json and
    hidden_payloads.json on the next write). Returns the updated item.

    Raises :class:`NotFoundError` if no mirror with that name exists.
    """
    payloads = load_payloads()
    item = next((p for p in payloads if p.get("name") == name), None)
    if item is None:
        raise NotFoundError(f"No payload named {name!r}.")

    item["hidden"] = bool(hidden)
    save_payloads(payloads)
    return reorder_item(item)
