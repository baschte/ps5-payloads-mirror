import { ApiError } from "./types";
import type {
  Payload,
  SchedulerStatus,
  UpdateAllResult,
  UpdateResult,
} from "./types";

/** Parse a FastAPI error response into an ApiError, including 422 candidates. */
async function toApiError(res: Response): Promise<ApiError> {
  let detail: unknown;
  try {
    detail = (await res.json())?.detail;
  } catch {
    detail = res.statusText;
  }
  if (detail && typeof detail === "object" && "message" in detail) {
    const d = detail as { message: string; candidates?: string[] };
    return new ApiError(d.message, res.status, d.candidates);
  }
  return new ApiError(
    typeof detail === "string" ? detail : `Request failed (${res.status})`,
    res.status,
  );
}

async function request<T>(input: string, init?: RequestInit): Promise<T> {
  const res = await fetch(input, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw await toApiError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function listPayloads(): Promise<Payload[]> {
  return request<Payload[]>("/api/payloads");
}

export function addPayload(body: {
  url: string;
  description?: string;
  extract_file?: string | null;
}): Promise<Payload> {
  return request<Payload>("/api/payloads", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updatePayload(name: string): Promise<UpdateResult> {
  return request<UpdateResult>(
    `/api/payloads/${encodeURIComponent(name)}/update`,
    { method: "POST" },
  );
}

export function updateAll(): Promise<UpdateAllResult[]> {
  return request<UpdateAllResult[]>("/api/payloads/update-all", {
    method: "POST",
  });
}

export function deletePayload(name: string): Promise<void> {
  return request<void>(`/api/payloads/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
}

export function getScheduler(): Promise<SchedulerStatus> {
  return request<SchedulerStatus>("/api/scheduler");
}

export function setScheduler(config: {
  enabled: boolean;
  interval_hours: number;
}): Promise<SchedulerStatus> {
  return request<SchedulerStatus>("/api/scheduler", {
    method: "PUT",
    body: JSON.stringify(config),
  });
}

export function runSchedulerNow(): Promise<SchedulerStatus> {
  return request<SchedulerStatus>("/api/scheduler/run-now", { method: "POST" });
}
