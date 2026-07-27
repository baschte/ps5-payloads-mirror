import type { Payload } from "./types";

export type SortColumn = "payload" | "version" | "updated" | "source";
export type SortDirection = "asc" | "desc";

export interface SortState {
  column: SortColumn;
  direction: SortDirection;
}

/** Sortable columns, in table order. Drives header rendering and validation of the persisted preference. */
export const SORT_COLUMNS: SortColumn[] = [
  "payload",
  "version",
  "updated",
  "source",
];

/** The label a row actually displays for a payload — sorting follows what the user sees. */
function label(p: Payload): string {
  return p.title ?? p.name;
}

function text(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

function timestamp(value: string | null | undefined): number | null {
  const raw = text(value);
  if (raw === null) return null;
  const parsed = Date.parse(raw);
  return Number.isNaN(parsed) ? null : parsed;
}

/** The value a column sorts on, or null when the payload has nothing to sort by. */
function sortValue(p: Payload, column: SortColumn): string | number | null {
  switch (column) {
    case "payload":
      return text(label(p));
    case "version":
      return text(p.version);
    case "updated":
      return timestamp(p.last_update);
    case "source":
      return text(p.source);
  }
}

function compareText(a: string, b: string): number {
  return a.localeCompare(b, undefined, { sensitivity: "base" });
}

/**
 * Compares release tags segment by segment so numeric parts compare numerically
 * (`v1.10.0` above `v1.9.0`). Deliberately heuristic rather than semver: upstream
 * tags in this collection include `v1.2`, `1.2.3b` and `20240115`, which a strict
 * parser would have to reject.
 */
function compareVersion(a: string, b: string): number {
  const left = a.split(/[^a-zA-Z0-9]+/).filter(Boolean);
  const right = b.split(/[^a-zA-Z0-9]+/).filter(Boolean);

  for (let i = 0; i < Math.min(left.length, right.length); i++) {
    const l = left[i];
    const r = right[i];
    const ln = Number(l);
    const rn = Number(r);

    if (!Number.isNaN(ln) && !Number.isNaN(rn)) {
      if (ln !== rn) return ln - rn;
      continue;
    }
    const diff = compareText(l, r);
    if (diff !== 0) return diff;
  }

  // Equal on every shared segment: the shorter tag is the earlier one.
  return left.length - right.length;
}

function compareValues(
  a: string | number,
  b: string | number,
  column: SortColumn,
): number {
  if (typeof a === "number" && typeof b === "number") return a - b;
  const l = String(a);
  const r = String(b);
  return column === "version" ? compareVersion(l, r) : compareText(l, r);
}

/**
 * Returns the payloads in the order the table should render them. Presentational
 * only — the caller keeps the unsorted list, so clearing the sort restores the
 * curated `sort_order` sequence without a refetch.
 *
 * Payloads with no value for the sorted column sink to the bottom in both
 * directions: an absent version isn't the smallest version, and flipping the
 * direction shouldn't bury the rows that have data. Remaining ties resolve by
 * name, so the rendered order never depends on a field that isn't visible.
 */
export function sortPayloads(
  payloads: Payload[],
  sort: SortState | null,
): Payload[] {
  if (!sort) return payloads;

  return [...payloads].sort((a, b) => {
    const va = sortValue(a, sort.column);
    const vb = sortValue(b, sort.column);

    if (va !== null && vb !== null) {
      const diff = compareValues(va, vb, sort.column);
      if (diff !== 0) return sort.direction === "asc" ? diff : -diff;
    } else if (va !== vb) {
      return va === null ? 1 : -1;
    }

    return compareText(a.name, b.name);
  });
}
