import { useCallback, useEffect, useRef, useState } from "react";
import { getScheduler, runSchedulerNow, setScheduler } from "../api";
import type { SchedulerStatus } from "../types";
import { IconBolt, IconPlay } from "./icons";

interface SchedulerPanelProps {
  onError: (message: string) => void;
  /** Called when a scheduled/manual run finishes, so the list can refresh. */
  onRunComplete: (summary: string) => void;
}

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatRelative(iso: string | null): string {
  if (!iso) return "";
  const diffMs = new Date(iso).getTime() - Date.now();
  if (diffMs <= 0) return "due now";
  const mins = Math.round(diffMs / 60000);
  if (mins < 60) return `in ~${mins} min`;
  const hours = Math.floor(mins / 60);
  const rem = mins % 60;
  return rem ? `in ~${hours}h ${rem}m` : `in ~${hours}h`;
}

export function SchedulerPanel({ onError, onRunComplete }: SchedulerPanelProps) {
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  // Form state is seeded once from the server; later polls only refresh the
  // display fields so they never clobber the user's unsaved edits.
  const [enabled, setEnabled] = useState(true);
  const [intervalHours, setIntervalHours] = useState(4);
  const [seeded, setSeeded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const lastRunRef = useRef<string | null>(null);

  const applyStatus = useCallback(
    (s: SchedulerStatus, seedForm: boolean) => {
      setStatus(s);
      if (seedForm) {
        setEnabled(s.enabled);
        setIntervalHours(s.interval_hours);
        setSeeded(true);
      }
      // Detect a completed run to trigger a list refresh upstream.
      if (lastRunRef.current !== null && s.last_run !== lastRunRef.current) {
        onRunComplete(s.last_summary ?? "Scheduled update finished.");
      }
      lastRunRef.current = s.last_run;
    },
    [onRunComplete],
  );

  // Effect: poll the scheduler status (external system) — faster while running.
  useEffect(() => {
    let cancelled = false;
    let timer: number;

    async function tick(seed: boolean) {
      try {
        const s = await getScheduler();
        if (!cancelled) applyStatus(s, seed);
      } catch {
        /* transient; next tick retries */
      }
      if (!cancelled) {
        const delay = status?.is_running ? 3000 : 15000;
        timer = window.setTimeout(() => tick(false), delay);
      }
    }

    void tick(true);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [applyStatus, status?.is_running]);

  const dirty =
    seeded &&
    status !== null &&
    (enabled !== status.enabled || intervalHours !== status.interval_hours);

  async function handleSave() {
    setSaving(true);
    try {
      applyStatus(await setScheduler({ enabled, interval_hours: intervalHours }), true);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to save schedule.");
    } finally {
      setSaving(false);
    }
  }

  async function handleRunNow() {
    setTriggering(true);
    try {
      applyStatus(await runSchedulerNow(), false);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to start update.");
    } finally {
      setTriggering(false);
    }
  }

  const running = status?.is_running ?? false;

  return (
    <section className="card flex h-full flex-col p-6" aria-labelledby="sched-heading">
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-50 text-brand-600 dark:text-brand-300">
            <IconBolt className="h-5 w-5" />
          </span>
          <h2 id="sched-heading" className="font-display text-lg font-semibold text-ink">
            Automatic updates
          </h2>
        </div>

        <label className="flex cursor-pointer items-center gap-2.5 select-none">
          <span className="sr-only">Enable automatic updates</span>
          <input
            type="checkbox"
            className="peer sr-only"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            disabled={!seeded || saving}
          />
          <span
            className="relative h-6 w-11 rounded-full bg-line-strong transition-colors
              after:absolute after:top-0.5 after:left-0.5 after:h-5 after:w-5 after:rounded-full
              after:bg-white after:shadow after:transition-transform after:content-['']
              peer-checked:bg-brand-500 peer-checked:after:translate-x-5
              peer-focus-visible:ring-2 peer-focus-visible:ring-brand-400 peer-focus-visible:ring-offset-2
              peer-focus-visible:ring-offset-surface"
            aria-hidden="true"
          />
          <span className="w-7 text-sm font-medium text-muted">
            {enabled ? "On" : "Off"}
          </span>
        </label>
      </div>

      <div className="flex-1">
        <div className="mb-2 flex items-baseline justify-between">
          <label htmlFor="interval" className="text-sm text-muted">
            Run every
          </label>
          <span className="font-mono text-sm font-semibold text-ink">
            {intervalHours} hour{intervalHours === 1 ? "" : "s"}
          </span>
        </div>
        <input
          id="interval"
          type="range"
          min={1}
          max={24}
          step={1}
          value={intervalHours}
          onChange={(e) => setIntervalHours(Number(e.target.value))}
          disabled={!enabled || !seeded || saving}
          className="h-2 w-full cursor-pointer appearance-none rounded-full bg-line-strong
            accent-brand-500 disabled:cursor-not-allowed disabled:opacity-40"
        />
        <div className="mt-1.5 flex justify-between font-mono text-[0.7rem] text-faint">
          <span>1h</span>
          <span>12h</span>
          <span>24h</span>
        </div>

        <dl className="mt-5 space-y-2.5 border-t border-line pt-4 text-sm">
          <div className="flex items-center justify-between">
            <dt className="text-muted">Status</dt>
            <dd>
              {running ? (
                <span className="chip bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500" />
                  Updating now
                </span>
              ) : enabled ? (
                <span className="chip bg-brand-50 text-brand-600 dark:text-brand-300">
                  <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
                  Scheduled
                </span>
              ) : (
                <span className="chip bg-paper text-faint">Disabled</span>
              )}
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-muted">Last run</dt>
            <dd className="text-right text-ink">
              {formatDateTime(status?.last_run ?? null)}
              {status?.last_summary && (
                <span className="block text-xs text-faint">{status.last_summary}</span>
              )}
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-muted">Next run</dt>
            <dd className="text-right text-ink">
              {enabled ? (
                <>
                  {formatDateTime(status?.next_run ?? null)}
                  <span className="block text-xs text-brand-600 dark:text-brand-300">
                    {formatRelative(status?.next_run ?? null)}
                  </span>
                </>
              ) : (
                "—"
              )}
            </dd>
          </div>
        </dl>
      </div>

      <div className="mt-5 flex gap-2.5">
        <button
          type="button"
          className="btn btn-md btn-primary flex-1"
          onClick={handleSave}
          disabled={!dirty || saving}
        >
          {saving ? "Saving…" : dirty ? "Save schedule" : "Saved"}
        </button>
        <button
          type="button"
          className="btn btn-md btn-ghost"
          onClick={handleRunNow}
          disabled={triggering || running}
        >
          <IconPlay className="h-4 w-4" />
          {running ? "Running…" : "Run now"}
        </button>
      </div>
    </section>
  );
}
