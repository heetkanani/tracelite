/**
 * API client for the tracelite backend.
 *
 * Wraps fetch with auth headers and JSON parsing.
 * Every function returns a typed promise.
 */
import { config } from "@/lib/config";
import type {
  TraceDetailResponse,
  TraceListResponse,
  EvalDefinitionItem,
  EvalDefinitionListResponse,
  EvalDefinitionCreatePayload,
  EvalDefinitionUpdatePayload,
  EvalRunSummary,
} from "@/lib/types";

// ----------------------------------------------------------------------
// Core fetch wrapper
// ----------------------------------------------------------------------

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(
  path: string,
  opts: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${config.apiBaseUrl}${path}`, {
    ...opts,
    headers: {
      ...opts.headers,
      "X-API-Key": config.apiKey,
    },
  });
  if (!res.ok) {
    throw new ApiError(
      res.status,
      `API ${res.status} on ${path}: ${await res.text()}`
    );
  }
  // 204 No Content has no body — return void without parsing.
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

// ----------------------------------------------------------------------
// Traces
// ----------------------------------------------------------------------

export interface TraceListFilters {
  status?: "ok" | "error";
  span_type?: "llm" | "tool" | "retrieval" | "generic";
  since?: string; // ISO 8601 UTC datetime
  has_failed_eval?: boolean;
}

export async function listTraces(params?: {
  cursor?: string;
  limit?: number;
  filters?: TraceListFilters;
}): Promise<TraceListResponse> {
  const qs = new URLSearchParams();
  if (params?.cursor) qs.set("cursor", params.cursor);
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.filters?.status) qs.set("status", params.filters.status);
  if (params?.filters?.span_type) qs.set("span_type", params.filters.span_type);
  if (params?.filters?.since) qs.set("since", params.filters.since);
  if (params?.filters?.has_failed_eval !== undefined) {
    qs.set("has_failed_eval", String(params.filters.has_failed_eval));
  }
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<TraceListResponse>(`/v1/traces${suffix}`);
}

export async function getTrace(traceId: string): Promise<TraceDetailResponse> {
  return apiFetch<TraceDetailResponse>(`/v1/traces/${traceId}`);
}

// ----------------------------------------------------------------------
// Evaluations
// ----------------------------------------------------------------------

export async function listEvals(params?: {
  activeOnly?: boolean;
}): Promise<EvalDefinitionListResponse> {
  const qs = params?.activeOnly ? "?active_only=true" : "";
  return apiFetch<EvalDefinitionListResponse>(`/v1/evals${qs}`);
}

export async function createEval(
  payload: EvalDefinitionCreatePayload
): Promise<EvalDefinitionItem> {
  return apiFetch<EvalDefinitionItem>("/v1/evals", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function updateEval(
  evalId: string,
  payload: EvalDefinitionUpdatePayload
): Promise<EvalDefinitionItem> {
  return apiFetch<EvalDefinitionItem>(`/v1/evals/${evalId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteEval(evalId: string): Promise<void> {
  return apiFetch<void>(`/v1/evals/${evalId}`, {
    method: "DELETE",
  });
}

export async function runEval(
  evalId: string,
  limit: number = 100
): Promise<EvalRunSummary> {
  return apiFetch<EvalRunSummary>(`/v1/evals/${evalId}/run?limit=${limit}`, {
    method: "POST",
  });
}