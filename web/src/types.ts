export interface Payload {
  name: string;
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

/** Error thrown by the API client; `candidates` is set for 422 ZIP-ambiguity. */
export class ApiError extends Error {
  status: number;
  candidates?: string[];

  constructor(message: string, status: number, candidates?: string[]) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.candidates = candidates;
  }
}
