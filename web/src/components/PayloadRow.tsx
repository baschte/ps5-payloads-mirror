import { useState } from "react";
import { deletePayload, updatePayload } from "../api";
import type { Payload } from "../types";
import { EditMirrorDialog } from "./EditMirrorDialog";
import {
  IconExternal,
  IconEye,
  IconEyeOff,
  IconGrip,
  IconPencil,
  IconSync,
  IconTrash,
} from "./icons";

interface PayloadRowProps {
  payload: Payload;
  busy: boolean;
  /** True while a column sort is active, which disables manual reordering. */
  sorted: boolean;
  /** Categories already in use across the current mirror list, offered as suggestions. */
  knownCategories: string[];
  onUpdated: (
    payload: Payload,
    message: string,
    changed: boolean,
    previousName?: string,
  ) => void;
  onRemoved: (name: string) => void;
  onError: (message: string) => void;
  setBusy: (busy: boolean) => void;
  onReorder: (draggedName: string, targetName: string) => void;
  onToggleHidden: (payload: Payload) => void;
}

export function PayloadRow({
  payload,
  busy,
  sorted,
  knownCategories,
  onUpdated,
  onRemoved,
  onError,
  setBusy,
  onReorder,
  onToggleHidden,
}: PayloadRowProps) {
  const [action, setAction] = useState<"update" | "remove" | null>(null);
  const [editing, setEditing] = useState(false);
  // Transient, purely visual drag state — local to this row, never lifted.
  const [dragging, setDragging] = useState(false);
  const [dropTarget, setDropTarget] = useState(false);

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

  // Reordering is only offered in the curated order: a drop applied to a sorted
  // view would persist that view as the new sort_order, silently discarding the
  // order the user curated by hand.
  const dragProps = sorted
    ? {}
    : {
        draggable: true,
        onDragStart: (e: React.DragEvent) => {
          e.dataTransfer.setData("text/plain", payload.name);
          e.dataTransfer.effectAllowed = "move";
          setDragging(true);
        },
        onDragEnd: () => setDragging(false),
        onDragOver: (e: React.DragEvent) => {
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
          if (!dropTarget) setDropTarget(true);
        },
        onDragLeave: () => setDropTarget(false),
        onDrop: (e: React.DragEvent) => {
          e.preventDefault();
          setDropTarget(false);
          const draggedName = e.dataTransfer.getData("text/plain");
          if (draggedName && draggedName !== payload.name) {
            onReorder(draggedName, payload.name);
          }
        },
      };

  return (
    <tr
      {...dragProps}
      className={`border-b border-line transition-colors last:border-0 hover:bg-paper/60 ${
        busy ? "opacity-55" : ""
      } ${dragging ? "opacity-40" : ""} ${
        dropTarget ? "bg-brand-50 dark:bg-brand-500/10" : ""
      } ${payload.hidden ? "opacity-50" : ""}`}
    >
      <td
        className={`px-3 py-4 align-top text-faint ${
          sorted ? "opacity-30" : "cursor-grab active:cursor-grabbing"
        }`}
        title={
          sorted
            ? "Clear the column sort to reorder mirrors manually"
            : "Drag to reorder"
        }
      >
        <IconGrip className="h-4 w-4" />
      </td>
      <td className="px-5 py-4 align-top">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-ink">{payload.title ?? payload.name}</span>
          {payload.hidden && (
            <span className="chip bg-paper text-faint">Hidden</span>
          )}
          {payload.category && (
            <span className="chip bg-paper text-faint">{payload.category}</span>
          )}
        </div>
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
            className="btn btn-sm btn-ghost"
            onClick={() => onToggleHidden(payload)}
            disabled={busy}
            aria-label={payload.hidden ? `Show ${payload.name}` : `Hide ${payload.name}`}
            title={payload.hidden ? "Show in published feed" : "Hide from published feed"}
          >
            {payload.hidden ? (
              <IconEyeOff className="h-3.5 w-3.5" />
            ) : (
              <IconEye className="h-3.5 w-3.5" />
            )}
          </button>
          <button
            type="button"
            className="btn btn-sm btn-ghost"
            onClick={() => setEditing(true)}
            disabled={busy}
            aria-label={`Edit ${payload.name}`}
          >
            <IconPencil className="h-3.5 w-3.5" />
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

      {editing && (
        <EditMirrorDialog
          payload={payload}
          knownCategories={knownCategories}
          onClose={() => setEditing(false)}
          onError={onError}
          onSaved={(saved) => {
            setEditing(false);
            onUpdated(saved, `${payload.name}: mirror updated.`, true, payload.name);
          }}
        />
      )}
    </tr>
  );
}
