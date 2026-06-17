"""In-process scheduler that periodically runs ``mirror_core.update_all``.

Runs entirely inside the FastAPI process (single asyncio task), so no external
scheduler/cron is needed — it fits the single-container deployment. The blocking
update work is offloaded to a thread so the event loop is never blocked, and it
shares ``mirror_core.DATA_LOCK`` with the API so a scheduled run can never
overlap a manual add/update/remove.

Configuration (enabled + interval) is persisted to a small JSON file so it
survives restarts.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import mirror_core

CONFIG_FILE = mirror_core.BASE_DIR / "scheduler_config.json"
DEFAULT_INTERVAL_HOURS = 4
MIN_INTERVAL_HOURS = 1
MAX_INTERVAL_HOURS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _run_update_locked() -> str:
    """Run a full update under the shared data lock. Returns a short summary."""
    with mirror_core.DATA_LOCK:
        results = mirror_core.update_all()
    changed = sum(1 for r in results if r.get("updated"))
    return f"{changed} of {len(results)} payloads updated"


class Scheduler:
    def __init__(self) -> None:
        self.enabled: bool = True
        self.interval_hours: int = DEFAULT_INTERVAL_HOURS
        self.last_run: datetime | None = None
        self.next_run: datetime | None = None
        self.last_summary: str | None = None
        self.is_running: bool = False

        self._task: asyncio.Task | None = None
        self._wake = asyncio.Event()
        self._load()

    # -- persistence ------------------------------------------------------- #
    def _load(self) -> None:
        try:
            data = json.loads(CONFIG_FILE.read_text())
            self.enabled = bool(data.get("enabled", self.enabled))
            self.interval_hours = self._clamp(
                int(data.get("interval_hours", self.interval_hours))
            )
        except (FileNotFoundError, ValueError, TypeError):
            pass

    def _save(self) -> None:
        CONFIG_FILE.write_text(
            json.dumps({"enabled": self.enabled, "interval_hours": self.interval_hours}, indent=2)
        )

    @staticmethod
    def _clamp(hours: int) -> int:
        return max(MIN_INTERVAL_HOURS, min(MAX_INTERVAL_HOURS, hours))

    # -- public state ------------------------------------------------------ #
    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "interval_hours": self.interval_hours,
            "is_running": self.is_running,
            "last_run": _iso(self.last_run),
            "next_run": _iso(self.next_run) if self.enabled else None,
            "last_summary": self.last_summary,
        }

    def _schedule_next(self) -> None:
        self.next_run = _now() + timedelta(hours=self.interval_hours) if self.enabled else None

    # -- lifecycle --------------------------------------------------------- #
    def start(self) -> None:
        self._schedule_next()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def update_config(self, enabled: bool, interval_hours: int) -> dict:
        self.enabled = enabled
        self.interval_hours = self._clamp(interval_hours)
        self._save()
        self._schedule_next()
        self._wake.set()  # interrupt the current wait so the new interval applies now
        return self.status()

    async def run_now(self) -> dict:
        """Trigger an update immediately (no-op if one is already running)."""
        if not self.is_running:
            asyncio.create_task(self._do_update())
        return self.status()

    # -- internals --------------------------------------------------------- #
    async def _do_update(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        try:
            self.last_summary = await asyncio.to_thread(_run_update_locked)
            self.last_run = _now()
        except Exception as e:  # never let the loop die on a single failure
            self.last_summary = f"Update failed: {e}"
            self.last_run = _now()
        finally:
            self.is_running = False
            self._schedule_next()

    async def _loop(self) -> None:
        while True:
            if not self.enabled or self.next_run is None:
                self._wake.clear()
                await self._wake.wait()
                continue

            timeout = max(0.0, (self.next_run - _now()).total_seconds())
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=timeout)
                # Woken by a config change: re-evaluate from the top.
                self._wake.clear()
                continue
            except asyncio.TimeoutError:
                await self._do_update()
