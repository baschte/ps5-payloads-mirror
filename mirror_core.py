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

BASE_DIR = Path(__file__).resolve().parent
JSON_FILE = BASE_DIR / "payloads.json"
PAYLOADS_DIR = BASE_DIR / "payloads"
README_FILE = BASE_DIR / "README.md"
BASE_URL = "https://github.com/baschte/ps5-payloads-mirror/releases/download/payloads-mirror"

MIRROR_OWNER = "baschte"
MIRROR_REPO = "ps5-payloads-mirror"

FIELD_ORDER = [
    "name", "filename", "url", "source", "source_direct",
    "asset_pattern", "extract_file", "description",
    "last_update", "version", "checksum",
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
# --------------------------------------------------------------------------- #
def load_payloads():
    """Load payloads.json, returning a list (empty if the file is missing)."""
    try:
        with open(JSON_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save_payloads(payloads):
    """Sort, reorder and persist payloads, then regenerate the README.

    Prefers an atomic write (temp file + ``os.replace``) so a concurrent reader
    never sees a half-written file. When the target is a Docker bind-mounted
    *file*, renaming onto it fails (``EBUSY``/``EXDEV`` — it's a mount point), so
    we fall back to an in-place write. Writers are serialized by ``DATA_LOCK``.
    """
    payloads.sort(key=lambda x: x.get("last_update", ""), reverse=True)
    payloads = [reorder_item(p) for p in payloads]
    data = json.dumps(payloads, indent=2)

    fd, tmp_path = tempfile.mkstemp(dir=str(BASE_DIR), suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(data)
        try:
            os.replace(tmp_path, JSON_FILE)
        except OSError:
            # Bind-mounted file: can't rename onto a mount point — write in place.
            with open(JSON_FILE, "w") as f:
                f.write(data)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    update_readme()
    return payloads


# --------------------------------------------------------------------------- #
# README generation
# --------------------------------------------------------------------------- #
def update_readme():
    """Regenerate the payload table inside README.md from payloads.json."""
    payloads = load_payloads()

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

    template = f"""# PS5 Payloads Mirror

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


def select_update_asset(assets, item):
    """Pick the best asset for an *existing* payload, mirroring the original
    scoring in update_payloads.py. Returns the asset dict or None."""
    repo_name = item.get("name", "")
    asset_pattern = item.get("asset_pattern")
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
        if asset_pattern and not re.search(asset_pattern, name, re.IGNORECASE):
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
    return selected if (selected and best > -1) else None


# --------------------------------------------------------------------------- #
# Public operations
# --------------------------------------------------------------------------- #
def add_payload(url, description="", extract_file=None):
    """Add a new mirror from a release ``url``. Returns the new payload dict.

    Raises :class:`MirrorError` / :class:`DuplicateError` / :class:`ZipExtractNeeded`.
    """
    url = (url or "").strip()
    if not url:
        raise MirrorError("URL is required.")

    domain, owner, repo = get_repo_info(url)
    if not owner:
        raise MirrorError("Could not parse Git domain/owner/repo from URL.")

    release = get_latest_release(domain, owner, repo)
    if not release:
        raise MirrorError(f"Could not fetch latest release for {owner}/{repo} on {domain}.")

    filename_match = re.search(r"/([^/]+\.(elf|bin|zip))$", url)
    original_filename = filename_match.group(1) if filename_match else None

    assets = release.get("assets", [])
    selected_asset = None
    if original_filename:
        selected_asset = next(
            (a for a in assets if a["name"] == original_filename), None
        )
    if not selected_asset and assets:
        selected_asset = next(
            (a for a in assets if a["name"].endswith((".elf", ".bin"))), None
        ) or next((a for a in assets if a["name"].endswith(".zip")), None)
    if not selected_asset:
        raise MirrorError("Could not find a suitable .elf, .bin or .zip asset in the latest release.")

    payloads = load_payloads()
    source_url = f"https://{domain}/{owner}/{repo}/releases"
    if any(p.get("source") == source_url for p in payloads):
        raise DuplicateError(f"A payload from {source_url} already exists.")

    gh_url = selected_asset["browser_download_url"]
    new_version = release["tag_name"]
    is_zip = selected_asset["name"].endswith(".zip")
    if is_zip:
        ext = "elf"
    else:
        ext = (selected_asset["name"].rsplit(".", 1)[1]
               if "." in selected_asset["name"] else "bin")

    filename = f"{repo}_{new_version}.{ext}"
    filepath = PAYLOADS_DIR / filename

    used_extract = None
    if is_zip:
        used_extract = _extract_zip_member(gh_url, filename, extract_file)
    else:
        if not download_file(gh_url, filename):
            raise MirrorError("Failed to download the payload asset.")

    new_item = {
        "name": repo,
        "filename": filename,
        "url": f"{BASE_URL}/{filename}",
        "source": source_url,
        "source_direct": gh_url,
        "description": (description or "").strip(),
        "last_update": release["published_at"][:10],
        "version": new_version,
        "checksum": calculate_checksum(filepath),
    }
    if used_extract:
        new_item["extract_file"] = used_extract

    payloads.append(new_item)
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

    selected_asset = select_update_asset(release["assets"], item)
    if not selected_asset:
        return {"updated": False, "item": reorder_item(item), "message": "No suitable asset found."}

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

    needs_download = (
        item.get("version") != new_version
        or item.get("filename") != new_filename
        or new_filename not in mirror_assets
    )
    if not needs_download:
        return {"updated": False, "item": reorder_item(item),
                "message": f"Already up to date ({new_version})."}

    # Remove the now-outdated local file.
    if item.get("filename") and item["filename"] != new_filename:
        old_path = PAYLOADS_DIR / item["filename"]
        if old_path.exists():
            old_path.unlink()

    extract_file = item.get("extract_file")
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
