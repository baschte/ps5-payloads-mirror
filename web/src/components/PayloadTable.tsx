import { PayloadRow } from "./PayloadRow";
import { IconArrowDown } from "./icons";
import type { Payload } from "../types";
import type { SortColumn, SortState } from "../sortPayloads";

interface PayloadTableProps {
  payloads: Payload[];
  busyName: string | null;
  sort: SortState | null;
  onToggleSort: (column: SortColumn) => void;
  /** Categories already in use across the current mirror list, offered as suggestions. */
  knownCategories: string[];
  onSetBusy: (name: string | null) => void;
  onUpdated: (
    payload: Payload,
    message: string,
    changed: boolean,
    previousName?: string,
  ) => void;
  onRemoved: (name: string) => void;
  onError: (message: string) => void;
  onReorder: (draggedName: string, targetName: string) => void;
  onToggleHidden: (payload: Payload) => void;
}

interface SortableHeaderProps {
  column: SortColumn;
  label: string;
  className: string;
  sort: SortState | null;
  onToggleSort: (column: SortColumn) => void;
}

/**
 * A header cell that cycles its column through ascending, descending and off.
 * The arrow stays in the layout on inactive columns (just transparent) so the
 * header row doesn't shift when the active column changes.
 */
function SortableHeader({
  column,
  label,
  className,
  sort,
  onToggleSort,
}: SortableHeaderProps) {
  const active = sort?.column === column;
  const descending = active && sort.direction === "desc";

  return (
    <th
      scope="col"
      className={className}
      aria-sort={
        active ? (descending ? "descending" : "ascending") : "none"
      }
    >
      <button
        type="button"
        className={`-mx-1.5 inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 uppercase tracking-wide transition-colors hover:text-ink ${
          active ? "text-ink" : ""
        }`}
        onClick={() => onToggleSort(column)}
        title={
          active
            ? descending
              ? `Sorted by ${label} descending — click to clear`
              : `Sorted by ${label} ascending — click to reverse`
            : `Sort by ${label}`
        }
      >
        {label}
        <IconArrowDown
          className={`h-3 w-3 transition ${active ? "opacity-100" : "opacity-0"} ${
            descending ? "" : "rotate-180"
          }`}
        />
      </button>
    </th>
  );
}

export function PayloadTable({
  payloads,
  busyName,
  sort,
  onToggleSort,
  knownCategories,
  onSetBusy,
  onUpdated,
  onRemoved,
  onError,
  onReorder,
  onToggleHidden,
}: PayloadTableProps) {
  if (payloads.length === 0) {
    return (
      <div className="card grid place-items-center px-6 py-16 text-center">
        <p className="font-display text-lg text-ink">No mirrors yet</p>
        <p className="mt-1 text-sm text-muted">Add one with the form above.</p>
      </div>
    );
  }

  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-line text-xs font-medium uppercase tracking-wide text-faint">
              <th scope="col" className="w-8 px-3 py-3.5">
                <span className="sr-only">Reorder</span>
              </th>
              <SortableHeader
                column="payload"
                label="Payload"
                className="px-5 py-3.5"
                sort={sort}
                onToggleSort={onToggleSort}
              />
              <SortableHeader
                column="version"
                label="Version"
                className="px-4 py-3.5"
                sort={sort}
                onToggleSort={onToggleSort}
              />
              <SortableHeader
                column="updated"
                label="Updated"
                className="hidden px-4 py-3.5 sm:table-cell"
                sort={sort}
                onToggleSort={onToggleSort}
              />
              <SortableHeader
                column="source"
                label="Source"
                className="hidden px-4 py-3.5 md:table-cell"
                sort={sort}
                onToggleSort={onToggleSort}
              />
              <th scope="col" className="px-5 py-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {payloads.map((p) => (
              <PayloadRow
                key={p.name}
                payload={p}
                busy={busyName === p.name}
                sorted={sort !== null}
                knownCategories={knownCategories}
                setBusy={(busy) => onSetBusy(busy ? p.name : null)}
                onUpdated={onUpdated}
                onRemoved={onRemoved}
                onError={onError}
                onReorder={onReorder}
                onToggleHidden={onToggleHidden}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
