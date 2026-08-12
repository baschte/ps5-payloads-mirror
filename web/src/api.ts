import { ApiError, UnauthorizedError } from "./types";
import type {
  Candidate,
  CollectionTitle,
  EditPayloadRequest,
  GitPushResult,
  GitStatus,
  Payload,
  SchedulerStatus,
  SessionStatus,
  UpdateAllResult,
  UpdateResult,
} from "./types";

/**
 * Notified whenever the backend rejects a call as unauthenticated, so the app
 * can return to the login screen from one place instead of every call site.
 *
 * Kept as a module-level slot rather than a React value because this module is
 * plain TypeScript — `AuthProvider` registers itself once on mount.
 */
type UnauthorizedHandler = () => void;

let onUnauthorized: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null) {
  onUnauthorized = handler;
}

/** Parse a FastAPI error response into an ApiError, including 422 candidates. */
async function toApiError(res: Response): Promise<ApiError> {
  let detail: unknown;
  try {
    detail = (await res.json())?.detail;
  } catch {
    detail = res.statusText;
  }
  if (detail && typeof detail === "object" && "message" in detail) {
    const d = detail as { message: string; candidates?: Candidate[] };
    return new ApiError(d.message, res.status, d.candidates);
  }
  return new ApiError(
    typeof detail === "string" ? detail : `Request failed (${res.status})`,
    res.status,
  );
}

interface RequestOptions {
  /**
   * Whether a 401 should trigger the global "session is gone" handler.
   * The auth endpoints opt out: their 401s are expected answers (not signed
   * in / wrong password) and are handled by the login screen itself.
   */
  handleUnauthorized?: boolean;
}

async function request<T>(
  input: string,
  init?: RequestInit,
  { handleUnauthorized = true }: RequestOptions = {},
): Promise<T> {
  const res = await fetch(input, {
    // The session lives in a same-origin HttpOnly cookie; being explicit here
    // documents that these calls are authenticated by it.
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (res.status === 401 && handleUnauthorized) {
    onUnauthorized?.();
    throw new UnauthorizedError();
  }
  if (!res.ok) throw await toApiError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// --------------------------------------------------------------------------- //
// Auth
// --------------------------------------------------------------------------- //

/** Current session. Rejects with a 401 ApiError when not signed in. */
export function getSession(): Promise<SessionStatus> {
  return request<SessionStatus>("/api/auth/me", undefined, {
    handleUnauthorized: false,
  });
}

export function login(
  username: string,
  password: string,
): Promise<SessionStatus> {
  return request<SessionStatus>(
    "/api/auth/login",
    { method: "POST", body: JSON.stringify({ username, password }) },
    { handleUnauthorized: false },
  );
}

export function logout(): Promise<SessionStatus> {
  return request<SessionStatus>(
    "/api/auth/logout",
    { method: "POST" },
    { handleUnauthorized: false },
  );
}

export function getTitle(): Promise<CollectionTitle> {
  return request<CollectionTitle>("/api/title");
}

export function setTitle(name: string): Promise<CollectionTitle> {
  return request<CollectionTitle>("/api/title", {
    method: "PUT",
    body: JSON.stringify({ name }),
  });
}

export function listPayloads(): Promise<Payload[]> {
  return request<Payload[]>("/api/payloads");
}

export function addPayload(body: {
  url: string;
  description?: string;
  title?: string;
  category?: string | null;
  asset_name?: string | null;
  extract_file?: string | null;
}): Promise<Payload> {
  return request<Payload>("/api/payloads", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function editPayload(
  name: string,
  body: EditPayloadRequest,
): Promise<Payload> {
  return request<Payload>(`/api/payloads/${encodeURIComponent(name)}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

/** Candidate files for a mirror's current (unchanged) source's latest release. */
export function getPayloadCandidates(name: string): Promise<Candidate[]> {
  return request<Candidate[]>(
    `/api/payloads/${encodeURIComponent(name)}/candidates`,
  );
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

/** Persist a full manual reorder — every known mirror name, once each, in the new order. */
export function reorderPayloads(names: string[]): Promise<Payload[]> {
  return request<Payload[]>("/api/payloads/reorder", {
    method: "PUT",
    body: JSON.stringify({ names }),
  });
}

export function setPayloadHidden(
  name: string,
  hidden: boolean,
): Promise<Payload> {
  return request<Payload>(`/api/payloads/${encodeURIComponent(name)}/hidden`, {
    method: "PUT",
    body: JSON.stringify({ hidden }),
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

export function getGitStatus(): Promise<GitStatus> {
  return request<GitStatus>("/api/git/status");
}

export function gitPush(): Promise<GitPushResult> {
  return request<GitPushResult>("/api/git/push", { method: "POST" });
}
