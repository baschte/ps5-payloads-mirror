import { useCallback, useEffect, useState } from "react";
import { SORT_COLUMNS } from "./sortPayloads";
import type { SortColumn, SortState } from "./sortPayloads";

const STORAGE_KEY = "payloadSort";

/** Reads the stored preference, treating anything unusable as "no sort". */
function readStored(): SortState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return null;
    const { column, direction } = parsed as Record<string, unknown>;
    if (!SORT_COLUMNS.includes(column as SortColumn)) return null;
    if (direction !== "asc" && direction !== "desc") return null;
    return { column: column as SortColumn, direction };
  } catch {
    return null;
  }
}

/**
 * The table's sort column and direction, persisted so the last chosen view
 * survives reloads. `null` means the curated `sort_order` from the backend.
 */
export function useSortPreference() {
  const [sort, setSort] = useState<SortState | null>(readStored);

  useEffect(() => {
    try {
      // The cleared state is stored explicitly, so "cleared it deliberately"
      // and "never chose one" both restore as the curated order.
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sort));
    } catch {
      /* storage unavailable — non-fatal */
    }
  }, [sort]);

  /** Cycles the given column: inactive → ascending → descending → cleared. */
  const toggle = useCallback((column: SortColumn) => {
    setSort((current) => {
      if (current?.column !== column) return { column, direction: "asc" };
      if (current.direction === "asc") return { column, direction: "desc" };
      return null;
    });
  }, []);

  return { sort, toggle };
}
