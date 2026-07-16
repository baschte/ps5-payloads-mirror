import { useState } from "react";
import { createPortal } from "react-dom";
import { editPayload, getPayloadCandidates } from "../api";
import { ApiError } from "../types";
import type { Candidate, Payload } from "../types";
import { CandidatePicker } from "./CandidatePicker";
import { IconX } from "./icons";

interface EditMirrorDialogProps {
  payload: Payload;
  onSaved: (payload: Payload) => void;
  onClose: () => void;
  onError: (message: string) => void;
}

/** Modal to edit an existing mirror's source URL, description, and asset/file selection. */
export function EditMirrorDialog({ payload, onSaved, onClose, onError }: EditMirrorDialogProps) {
  const [url, setUrl] = useState(payload.source ?? "");
  const [title, setTitle] = useState(payload.title ?? payload.name);
  const [description, setDescription] = useState(payload.description ?? "");
  const [candidates, setCandidates] = useState<Candidate[] | null>(null);
  const [chosen, setChosen] = useState<Candidate | null>(null);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleChangeFile() {
    setLoadingCandidates(true);
    try {
      const list = await getPayloadCandidates(payload.name);
      setCandidates(list);
      // Pre-select the mirror's current asset/file if it's still among the candidates.
      const current = list.find(
        (c) =>
          c.asset_name === payload.asset_pattern &&
          c.member_name === (payload.extract_file ?? null),
      );
      setChosen(current ?? (list.length === 1 ? list[0] : null));
    } catch (err) {
      onError(
        err instanceof Error ? err.message : "Failed to load candidate files.",
      );
    } finally {
      setLoadingCandidates(false);
    }
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!url.trim() || submitting) return;
    if (candidates && !chosen) return;

    setSubmitting(true);
    try {
      const saved = await editPayload(payload.name, {
        url: url.trim(),
        title: title.trim(),
        description: description.trim(),
        asset_name: chosen?.asset_name ?? null,
        extract_file: chosen?.member_name ?? null,
      });
      onSaved(saved);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422 && err.candidates) {
        // Release has multiple plausible files: surface the choices and ask again.
        setCandidates(err.candidates);
        onError(err.message);
      } else {
        onError(err instanceof Error ? err.message : "Failed to save mirror.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4"
      onClick={onClose}
    >
      <form
        className="card w-full max-w-md p-6"
        onClick={(e) => e.stopPropagation()}
        onSubmit={handleSubmit}
      >
        <div className="mb-5 flex items-center justify-between">
          <h2 className="font-display text-lg font-semibold text-ink">
            Edit {payload.name}
          </h2>
          <button
            type="button"
            className="btn btn-ghost h-9 w-9 !px-0"
            onClick={onClose}
            aria-label="Close"
          >
            <IconX className="h-4 w-4" />
          </button>
        </div>

        <div className="flex flex-col gap-4">
          <div>
            <label className="label" htmlFor="edit-mirror-url">
              Release URL
            </label>
            <input
              id="edit-mirror-url"
              type="url"
              required
              className="input"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={submitting}
            />
          </div>

          <div>
            <label className="label" htmlFor="edit-mirror-title">
              Title <span className="font-normal text-faint">(optional)</span>
            </label>
            <input
              id="edit-mirror-title"
              type="text"
              className="input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={submitting}
            />
          </div>

          <div>
            <label className="label" htmlFor="edit-mirror-desc">
              Description <span className="font-normal text-faint">(optional)</span>
            </label>
            <input
              id="edit-mirror-desc"
              type="text"
              className="input"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={submitting}
            />
          </div>

          {candidates ? (
            <CandidatePicker
              id="edit-mirror-candidate"
              candidates={candidates}
              value={chosen}
              onChange={setChosen}
              disabled={submitting}
            />
          ) : (
            <div>
              <label className="label">
                Asset{" "}
                <span className="font-normal text-faint">
                  ({payload.asset_pattern ?? payload.filename ?? "current file"})
                </span>
              </label>
              <button
                type="button"
                className="btn btn-sm btn-ghost"
                onClick={handleChangeFile}
                disabled={submitting || loadingCandidates}
              >
                {loadingCandidates ? "Loading…" : "Change file…"}
              </button>
            </div>
          )}
        </div>

        <div className="mt-5 flex gap-2.5">
          <button
            type="button"
            className="btn btn-md btn-ghost flex-1"
            onClick={onClose}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="btn btn-md btn-primary flex-1"
            disabled={submitting || (candidates !== null && !chosen)}
          >
            {submitting ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
    </div>,
    document.body,
  );
}
