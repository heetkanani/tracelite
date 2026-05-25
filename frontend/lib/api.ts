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
} from "@/lib/types";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const url = `${config.apiBaseUrl}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "X-API-Key": config.apiKey,
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(
      res.status,
      `API ${res.status} on ${path}: ${text || res.statusText}`
    );
  }

  return res.json() as Promise<T>;
}

// -------- Trace list -----------------------------------------------------

export interface TraceListFilters {
  status?: "ok" | "error";
  span_type?: "llm" | "tool" | "retrieval" | "generic";
  since?: string; // ISO 8601 UTC datetime
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
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<TraceListResponse>(`/v1/traces${suffix}`);
}

// -------- Trace detail ---------------------------------------------------

export async function getTrace(traceId: string): Promise<TraceDetailResponse> {
  return apiFetch<TraceDetailResponse>(`/v1/traces/${traceId}`);
}