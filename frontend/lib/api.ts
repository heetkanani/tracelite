/**
 * API client for the tracelite backend.
 *
 * Wraps fetch with auth handling and JSON parsing.
 * Every function returns a typed promise.
 *
 * Authentication: sends cookies (credentials: "include") so the
 * tracelite_session cookie set by /v1/auth/login is automatically
 * attached. The X-API-Key header is only used for SDK ingestion paths;
 * the dashboard relies on the session cookie alone.
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
  AlertRuleItem,
  AlertRuleListResponse,
  AlertRuleCreatePayload,
  AlertRuleUpdatePayload,
  AlertEventListResponse,
  UserResponse,
  SessionResponse,
  SignupRequest,
  LoginRequest,
  ApiKeyCreated,
  ApiKeyItem,
} from "@/lib/types";

// ----------------------------------------------------------------------
// Errors
// ----------------------------------------------------------------------

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Thrown specifically on 401 responses. The auth provider catches this
 * and redirects to /login. Routes that handle 401 themselves (e.g.,
 * /login checking if the user is already logged in) can catch this
 * subclass and ignore it.
 */
export class UnauthorizedError extends ApiError {
  constructor(message: string) {
    super(401, message);
    this.name = "UnauthorizedError";
  }
}

// ----------------------------------------------------------------------
// Core fetch wrapper
// ----------------------------------------------------------------------

export async function apiFetch<T>(
  path: string,
  opts: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${config.apiBaseUrl}${path}`, {
    ...opts,
    credentials: "include", // send tracelite_session cookie
    headers: {
      "Content-Type": "application/json",
      ...opts.headers,
    },
  });

  if (res.status === 401) {
    // Try to surface the server's detail; fall back to a generic message.
    let detail = "Not authenticated";
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // Body not JSON — keep generic.
    }
    throw new UnauthorizedError(detail);
  }

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

// ----------------------------------------------------------------------
// Alerts
// ----------------------------------------------------------------------

export async function listAlerts(): Promise<AlertRuleListResponse> {
  return apiFetch<AlertRuleListResponse>("/v1/alerts");
}

export async function createAlert(
  payload: AlertRuleCreatePayload
): Promise<AlertRuleItem> {
  return apiFetch<AlertRuleItem>("/v1/alerts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function updateAlert(
  ruleId: string,
  payload: AlertRuleUpdatePayload
): Promise<AlertRuleItem> {
  return apiFetch<AlertRuleItem>(`/v1/alerts/${ruleId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteAlert(ruleId: string): Promise<void> {
  return apiFetch<void>(`/v1/alerts/${ruleId}`, {
    method: "DELETE",
  });
}

export async function listAlertEvents(
  limit: number = 50
): Promise<AlertEventListResponse> {
  return apiFetch<AlertEventListResponse>(`/v1/alert_events?limit=${limit}`);
}

export async function testAlert(ruleId: string): Promise<{
  delivered: boolean;
  error_message: string | null;
  message: string;
}> {
  return apiFetch(`/v1/alerts/${ruleId}/test`, { method: "POST" });
}

// ----------------------------------------------------------------------
// Auth
// ----------------------------------------------------------------------

export async function signup(
  payload: SignupRequest
): Promise<SessionResponse> {
  return apiFetch<SessionResponse>("/v1/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function login(
  payload: LoginRequest
): Promise<SessionResponse> {
  return apiFetch<SessionResponse>("/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function logout(): Promise<void> {
  return apiFetch<void>("/v1/auth/logout", {
    method: "POST",
  });
}

export async function getMe(): Promise<UserResponse> {
  return apiFetch<UserResponse>("/v1/auth/me");
}


// --- API Keys ---

export async function listApiKeys(): Promise<ApiKeyItem[]> {
  return apiFetch("/v1/api-keys");
}

export async function createApiKey(name: string): Promise<ApiKeyCreated> {
  return apiFetch("/v1/api-keys", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function deleteApiKey(id: string): Promise<void> {
  return apiFetch(`/v1/api-keys/${id}`, { method: "DELETE" });
}