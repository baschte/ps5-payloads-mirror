export interface Payload {
  name: string;
  title?: string | null;
  filename?: string | null;
  url?: string | null;
  source?: string | null;
  source_direct?: string | null;
  asset_pattern?: string | null;
  extract_file?: string | null;
  description?: string | null;
  last_update?: string | null;
  version?: string | null;
  checksum?: string | null;
  sort_order?: number | null;
  hidden: boolean;
}

export interface UpdateResult {
  updated: boolean;
  item: Payload;
  message: string;
}

export interface UpdateAllResult extends UpdateResult {
  name: string;
}

export interface SchedulerStatus {
  enabled: boolean;
  interval_hours: number;
  is_running: boolean;
  last_run: string | null;
  next_run: string | null;
  last_summary: string | null;
}

export interface CollectionTitle {
  name: string;
}

export interface GitStatus {
  enabled: boolean;
  pending: boolean;
}

export interface GitPushResult {
  committed: boolean;
  pushed: boolean;
  message: string;
}

/** One selectable candidate file for an ambiguous release (top-level asset, or a member inside a ZIP asset). */
export interface Candidate {
  asset_name: string;
  member_name: string | null;
  label: string;
}

export interface EditPayloadRequest {
  url?: string;
  description?: string;
  title?: string;
  asset_name?: string | null;
  extract_file?: string | null;
}

/** Error thrown by the API client; `candidates` is set for 422 candidate-ambiguity. */
export class ApiError extends Error {
  status: number;
  candidates?: Candidate[];

  constructor(message: string, status: number, candidates?: Candidate[]) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.candidates = candidates;
  }
}
