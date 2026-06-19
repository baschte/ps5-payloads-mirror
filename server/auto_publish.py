"""Auto-publish: debounced commit & push after payloads.json changes.

When the mirror data changes — whether from a manual edit via the web UI or from
a scheduled update — we wait a short debounce window (default 60s) and then run
``git_ops.commit_and_push`` automatically, so publishing no longer requires a
manual button press.

Mechanism:
- ``mirror_core`` calls every registered post-write hook after each successful
  write of payloads.json. We register :meth:`AutoPublisher.notify_change`, which
  is thread-safe (writes happen in FastAPI's worker threadpool and in the
  scheduler's worker thread, not on the event loop).
- Each notification (re)arms a single debounce timer on the event loop. Multiple
  changes inside the window coalesce into one publish.
- When the timer fires, the commit & push runs in a worker thread under
  ``mirror_core.DATA_LOCK`` (same as the manual ``/api/git/push`` path), so it
  never overlaps a data mutation.

Only active when git push is configured (``git_ops.push_enabled()``) and not
disabled via ``AUTO_PUBLISH_ENABLED=0``. The delay is configurable via
``AUTO_PUBLISH_DELAY_SECONDS`` (default 60).
"""

import asyncio
import os

import mirror_core
from server import git_ops


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


DEFAULT_DELAY_SECONDS = _env_int("AUTO_PUBLISH_DELAY_SECONDS", 60)
ENABLED = os.environ.get("AUTO_PUBLISH_ENABLED", "1") not in ("0", "false", "False", "")


def _publish_locked() -> str:
    """Commit & push pending changes under the shared data lock."""
    with mirror_core.DATA_LOCK:
        if not git_ops.has_changes():
            return "Nothing to publish."
        return git_ops.commit_and_push()["message"]


class AutoPublisher:
    def __init__(self, delay_seconds: int = DEFAULT_DELAY_SECONDS) -> None:
        self.delay_seconds = delay_seconds
        self.last_result: str | None = None
        self.is_publishing: bool = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._timer: asyncio.TimerHandle | None = None
        self._task: asyncio.Task | None = None

    # -- lifecycle --------------------------------------------------------- #
    def start(self) -> None:
        if not ENABLED:
            return
        self._loop = asyncio.get_running_loop()
        mirror_core.register_post_write_hook(self.notify_change)

    async def stop(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    # -- public state ------------------------------------------------------ #
    def status(self) -> dict:
        return {
            "enabled": ENABLED and git_ops.push_enabled(),
            "delay_seconds": self.delay_seconds,
            "is_publishing": self.is_publishing,
            "pending": self._timer is not None,
            "last_result": self.last_result,
        }

    # -- change notification (thread-safe) --------------------------------- #
    def notify_change(self) -> None:
        """Arm/refresh the debounce timer. Safe to call from any thread."""
        loop = self._loop
        if loop is None or not git_ops.push_enabled():
            return
        loop.call_soon_threadsafe(self._arm)

    # -- internals (event loop only) --------------------------------------- #
    def _arm(self) -> None:
        if self._timer:
            self._timer.cancel()
        self._timer = self._loop.call_later(self.delay_seconds, self._fire)

    def _fire(self) -> None:
        self._timer = None
        if self._task and not self._task.done():
            # A publish is still running — re-arm so this round's changes get
            # their own publish once the current one finishes.
            self._arm()
            return
        self._task = asyncio.create_task(self._publish())

    async def _publish(self) -> None:
        self.is_publishing = True
        try:
            self.last_result = await asyncio.to_thread(_publish_locked)
        except Exception as e:  # GitError or anything unexpected
            self.last_result = f"Auto-publish failed: {e}"
        finally:
            self.is_publishing = False
