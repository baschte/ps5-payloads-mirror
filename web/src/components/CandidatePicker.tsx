import type { Candidate } from "../types";

interface CandidatePickerProps {
  candidates: Candidate[];
  value: Candidate | null;
  onChange: (candidate: Candidate | null) => void;
  disabled?: boolean;
  id?: string;
}

/**
 * Shared "which file, exactly" picker for add/edit: a flattened list of
 * plausible top-level assets and ZIP-nested members, shown whenever a
 * release has more than one candidate.
 */
export function CandidatePicker({
  candidates,
  value,
  onChange,
  disabled,
  id = "candidate-picker",
}: CandidatePickerProps) {
  return (
    <div className="animate-fade rounded-xl border border-amber-200 bg-amber-50/70 p-3 dark:border-amber-500/30 dark:bg-amber-500/10">
      <label className="label text-amber-700 dark:text-amber-300" htmlFor={id}>
        This release has multiple candidate files — pick one
      </label>
      <select
        id={id}
        className="input"
        value={value ? value.label : ""}
        onChange={(e) => {
          const next = candidates.find((c) => c.label === e.target.value) ?? null;
          onChange(next);
        }}
        disabled={disabled}
      >
        <option value="">Select a file…</option>
        {candidates.map((c) => (
          <option key={c.label} value={c.label}>
            {c.label}
          </option>
        ))}
      </select>
    </div>
  );
}
