import { useState } from "react";
import { addPayload } from "../api";
import { ApiError } from "../types";
import type { Payload } from "../types";
import { IconPlus } from "./icons";

interface AddMirrorFormProps {
  onAdded: (payload: Payload) => void;
  onError: (message: string) => void;
}

/** Controlled form to add a new mirror from an upstream release URL. */
export function AddMirrorForm({ onAdded, onError }: AddMirrorFormProps) {
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [extractFile, setExtractFile] = useState("");
  const [candidates, setCandidates] = useState<string[] | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!url.trim() || submitting) return;

    setSubmitting(true);
    try {
      const payload = await addPayload({
        url: url.trim(),
        description: description.trim(),
        extract_file: extractFile.trim() || null,
      });
      onAdded(payload);
      setUrl("");
      setDescription("");
      setExtractFile("");
      setCandidates(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422 && err.candidates) {
        // ZIP with multiple .elf files: surface the choices and ask again.
        setCandidates(err.candidates);
        onError(err.message);
      } else {
        onError(err instanceof Error ? err.message : "Failed to add mirror.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="card flex h-full flex-col p-6" onSubmit={handleSubmit}>
      <div className="mb-5 flex items-center gap-2.5">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-50 text-brand-600 dark:text-brand-300">
          <IconPlus className="h-5 w-5" />
        </span>
        <h2 className="font-display text-lg font-semibold text-ink">Add mirror</h2>
      </div>

      <div className="flex flex-1 flex-col gap-4">
        <div>
          <label className="label" htmlFor="mirror-url">
            Release URL
          </label>
          <input
            id="mirror-url"
            type="url"
            required
            className="input"
            placeholder="https://github.com/owner/repo/releases"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={submitting}
          />
        </div>

        <div>
          <label className="label" htmlFor="mirror-desc">
            Description <span className="font-normal text-faint">(optional)</span>
          </label>
          <input
            id="mirror-desc"
            type="text"
            className="input"
            placeholder="What does this payload do?"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={submitting}
          />
        </div>

        {candidates && (
          <div className="animate-fade rounded-xl border border-amber-200 bg-amber-50/70 p-3 dark:border-amber-500/30 dark:bg-amber-500/10">
            <label className="label text-amber-700 dark:text-amber-300" htmlFor="mirror-extract">
              This ZIP has several .elf files — pick one
            </label>
            <select
              id="mirror-extract"
              className="input"
              value={extractFile}
              onChange={(e) => setExtractFile(e.target.value)}
              disabled={submitting}
            >
              <option value="">Select a file…</option>
              {candidates.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <button
        type="submit"
        className="btn btn-md btn-primary mt-5 w-full"
        disabled={submitting}
      >
        {submitting ? "Adding…" : "Add mirror"}
      </button>
    </form>
  );
}
