import { PayloadRow } from "./PayloadRow";
import type { Payload } from "../types";

interface PayloadTableProps {
  payloads: Payload[];
  busyName: string | null;
  onSetBusy: (name: string | null) => void;
  onUpdated: (payload: Payload, message: string, changed: boolean) => void;
  onRemoved: (name: string) => void;
  onError: (message: string) => void;
}

export function PayloadTable({
  payloads,
  busyName,
  onSetBusy,
  onUpdated,
  onRemoved,
  onError,
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
              <th scope="col" className="px-5 py-3.5">Payload</th>
              <th scope="col" className="px-4 py-3.5">Version</th>
              <th scope="col" className="hidden px-4 py-3.5 sm:table-cell">Updated</th>
              <th scope="col" className="hidden px-4 py-3.5 md:table-cell">Source</th>
              <th scope="col" className="px-5 py-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {payloads.map((p) => (
              <PayloadRow
                key={p.name}
                payload={p}
                busy={busyName === p.name}
                setBusy={(busy) => onSetBusy(busy ? p.name : null)}
                onUpdated={onUpdated}
                onRemoved={onRemoved}
                onError={onError}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
