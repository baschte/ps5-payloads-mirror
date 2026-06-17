import { useState } from "react";
import { deletePayload, updatePayload } from "../api";
import type { Payload } from "../types";
import { IconExternal, IconSync, IconTrash } from "./icons";

interface PayloadRowProps {
  payload: Payload;
  busy: boolean;
  onUpdated: (payload: Payload, message: string, changed: boolean) => void;
  onRemoved: (name: string) => void;
  onError: (message: string) => void;
  setBusy: (busy: boolean) => void;
}

export function PayloadRow({
  payload,
  busy,
  onUpdated,
  onRemoved,
  onError,
  setBusy,
}: PayloadRowProps) {
  const [action, setAction] = useState<"update" | "remove" | null>(null);

  async function handleUpdate() {
    setBusy(true);
    setAction("update");
    try {
      const res = await updatePayload(payload.name);
      onUpdated(res.item, `${payload.name}: ${res.message}`, res.updated);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Update failed.");
    } finally {
      setBusy(false);
      setAction(null);
    }
  }

  async function handleRemove() {
    if (!window.confirm(`Remove mirror "${payload.name}"? This deletes the local file.`)) {
      return;
    }
    setBusy(true);
    setAction("remove");
    try {
      await deletePayload(payload.name);
      onRemoved(payload.name);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Remove failed.");
    } finally {
      setBusy(false);
      setAction(null);
    }
  }

  return (
    <tr
      className={`border-b border-line transition-colors last:border-0 hover:bg-paper/60 ${
        busy ? "opacity-55" : ""
      }`}
    >
      <td className="px-5 py-4 align-top">
        <div className="font-semibold text-ink">{payload.name}</div>
        {payload.description && (
          <div className="mt-0.5 line-clamp-2 max-w-[44ch] text-xs leading-relaxed text-muted">
            {payload.description}
          </div>
        )}
      </td>
      <td className="px-4 py-4 align-top">
        <span className="inline-flex rounded-md bg-paper px-2 py-1 font-mono text-xs text-ink ring-1 ring-line-strong">
          {payload.version ?? "—"}
        </span>
      </td>
      <td className="hidden px-4 py-4 align-top text-muted sm:table-cell">
        {payload.last_update ?? "—"}
      </td>
      <td className="hidden px-4 py-4 align-top md:table-cell">
        {payload.source ? (
          <a
            href={payload.source}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1 text-brand-600 transition-colors hover:text-brand-700 dark:text-brand-300 dark:hover:text-brand-200"
          >
            Source
            <IconExternal className="h-3.5 w-3.5" />
          </a>
        ) : (
          "—"
        )}
      </td>
      <td className="px-5 py-4 align-top">
        <div className="flex justify-end gap-2">
          <button
            type="button"
            className="btn btn-sm btn-ghost"
            onClick={handleUpdate}
            disabled={busy}
          >
            <IconSync className={`h-3.5 w-3.5 ${action === "update" ? "animate-spin" : ""}`} />
            {action === "update" ? "Updating" : "Update"}
          </button>
          <button
            type="button"
            className="btn btn-sm btn-danger"
            onClick={handleRemove}
            disabled={busy}
            aria-label={`Remove ${payload.name}`}
          >
            <IconTrash className="h-3.5 w-3.5" />
          </button>
        </div>
      </td>
    </tr>
  );
}
