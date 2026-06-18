"""Commit & push the mirror data (payloads.json + README.md) to GitHub.

Enabled only when all four env vars are set:
  GIT_USERNAME, GIT_PASSWORD, GIT_AUTHOR_NAME, GIT_AUTHOR_EMAIL

Security model:
- The endpoint sits behind the app's Basic Auth (see server/main.py).
- The password/token is handed to git via a one-shot credential helper that
  reads it from the *subprocess environment* — never written to disk, never put
  in argv (so it can't leak via `ps`), and never persisted in the remote URL.
- Any git output returned to the client is scrubbed of the token.
- A `git pull --rebase` is always run before pushing; on conflict the rebase is
  aborted and an error is returned (never a force-push).
"""

import os
import re
import subprocess

import mirror_core

GIT_USERNAME = os.environ.get("GIT_USERNAME", "")
GIT_PASSWORD = os.environ.get("GIT_PASSWORD", "")
GIT_AUTHOR_NAME = os.environ.get("GIT_AUTHOR_NAME", "")
GIT_AUTHOR_EMAIL = os.environ.get("GIT_AUTHOR_EMAIL", "")

COMMIT_FILES = ["payloads.json", "README.md"]
COMMIT_MESSAGE = "Update payloads metadata via web UI"

# Credential helper: git runs the `!...` value via a shell, which expands the
# env vars we pass in the subprocess environment. The secret value itself never
# appears in this string (only the variable names).
_CRED_HELPER = '!f() { echo "username=$GIT_USERNAME"; echo "password=$GIT_PASSWORD"; }; f'


class GitError(Exception):
    """Recoverable git problem (maps to HTTP 400)."""


def _env_configured() -> bool:
    return all([GIT_USERNAME, GIT_PASSWORD, GIT_AUTHOR_NAME, GIT_AUTHOR_EMAIL])


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def is_repo() -> bool:
    return (mirror_core.BASE_DIR / ".git").exists()


def push_enabled() -> bool:
    return _env_configured() and _git_available() and is_repo()


def _run(args, network=False):
    base = ["git", "-C", str(mirror_core.BASE_DIR), "-c", "safe.directory=*"]
    env = dict(os.environ)
    if network:
        # Clear any inherited helper, then install ours; supply secrets via env.
        base += ["-c", "credential.helper=", "-c", f"credential.helper={_CRED_HELPER}"]
        env["GIT_USERNAME"] = GIT_USERNAME
        env["GIT_PASSWORD"] = GIT_PASSWORD
    return subprocess.run(base + args, capture_output=True, text=True, env=env, timeout=120)


def _sanitize(text: str) -> str:
    if not text:
        return ""
    if GIT_PASSWORD:
        text = text.replace(GIT_PASSWORD, "***")
    return text.strip()


def _https_remote() -> str:
    res = _run(["remote", "get-url", "origin"])
    if res.returncode != 0:
        raise GitError("No 'origin' remote is configured.")
    url = res.stdout.strip()
    m = re.match(r"git@([^:]+):(.+?)(?:\.git)?$", url)
    if m:
        return f"https://{m.group(1)}/{m.group(2)}.git"
    m = re.match(r"https?://(?:[^@/]+@)?([^/]+)/(.+?)(?:\.git)?$", url)
    if m:
        return f"https://{m.group(1)}/{m.group(2)}.git"
    raise GitError("Unsupported 'origin' remote URL (expected GitHub HTTPS or SSH).")


def _current_branch() -> str:
    res = _run(["rev-parse", "--abbrev-ref", "HEAD"])
    branch = res.stdout.strip()
    if res.returncode != 0 or not branch or branch == "HEAD":
        raise GitError("Could not determine the current branch (detached HEAD?).")
    return branch


def commit_and_push() -> dict:
    """Stage the data files, commit, rebase onto the remote, and push.

    Returns ``{committed, pushed, message}``; raises :class:`GitError`.
    """
    if not _env_configured():
        raise GitError(
            "Git push is not configured. Set GIT_USERNAME, GIT_PASSWORD, "
            "GIT_AUTHOR_NAME and GIT_AUTHOR_EMAIL."
        )
    if not _git_available():
        raise GitError("git is not available in this environment.")
    if not is_repo():
        raise GitError("Not a git repository — mount the repo into the container (see WEBUI.md).")

    # Clean up a rebase left in progress by a previous failed attempt, so the
    # repo isn't permanently stuck on a server with no shell access.
    git_dir = mirror_core.BASE_DIR / ".git"
    if (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists():
        _run(["rebase", "--abort"])

    branch = _current_branch()
    remote = _https_remote()

    add = _run(["add", "--"] + COMMIT_FILES)
    if add.returncode != 0:
        raise GitError(_sanitize(add.stderr) or "git add failed.")

    # Nothing staged → nothing to publish.
    if _run(["diff", "--cached", "--quiet"]).returncode == 0:
        return {"committed": False, "pushed": False, "message": "No changes to publish."}

    commit = _run([
        "-c", f"user.name={GIT_AUTHOR_NAME}",
        "-c", f"user.email={GIT_AUTHOR_EMAIL}",
        "commit", "-m", COMMIT_MESSAGE,
    ])
    if commit.returncode != 0:
        raise GitError(_sanitize(commit.stderr) or "git commit failed.")

    # MUST rebase onto the latest remote before pushing. payloads.json and
    # README.md are generated artifacts, and a parallel writer (the daily
    # GitHub Action) commits the same files — so a plain rebase would conflict.
    # "-X theirs" auto-resolves in favour of the commit being replayed (our
    # current UI state wins), which is the intended "publish my state" behaviour.
    pull = _run([
        "-c", f"user.name={GIT_AUTHOR_NAME}",
        "-c", f"user.email={GIT_AUTHOR_EMAIL}",
        "pull", "--rebase", "-X", "theirs", remote, branch,
    ], network=True)
    if pull.returncode != 0:
        _run(["rebase", "--abort"])  # best-effort cleanup, leaves the commit intact
        raise GitError(
            "git pull --rebase failed — could not auto-resolve. " + _sanitize(pull.stderr)
        )

    push = _run(["push", remote, f"HEAD:{branch}"], network=True)
    if push.returncode != 0:
        raise GitError("git push failed. " + _sanitize(push.stderr))

    return {"committed": True, "pushed": True, "message": f"Committed & pushed to {branch}."}
