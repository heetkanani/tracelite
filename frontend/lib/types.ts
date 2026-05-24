/**
 * TypeScript types mirroring the backend's Pydantic models.
 *
 * Keep these in sync with backend/app/models.py. When the backend
 * changes, change here too and let the compiler find every callsite.
 */

export type SpanType = "llm" | "tool" | "retrieval" | "generic";
export type SpanStatus = "ok" | "error";

export interface TraceListItem {
  id: string;
  name: string | null;
  user_id: string | null;
  session_id: string | null;
  started_at: string;
  ended_at: string | null;
  metadata: Record<string, unknown>;

  // Aggregates from the list query (zero/null on detail endpoint).
  span_count: number;
  total_cost_usd: number;
  max_duration_ms: number | null;
  has_error: boolean;
}

export interface TraceListResponse {
  items: TraceListItem[];
  next_cursor: string | null;
}

export interface SpanItem {
  id: string;
  trace_id: string;
  parent_span_id: string | null;
  name: string;
  span_type: SpanType;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  model: string | null;
  input: unknown;
  output: unknown;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: number | null;
  status: SpanStatus;
  error_message: string | null;
  attributes: Record<string, unknown>;
}

export interface TraceDetailResponse {
  trace: TraceListItem;
  spans: SpanItem[];
}