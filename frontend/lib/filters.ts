"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

import type { TraceListFilters } from "@/lib/api";

// ----------------------------------------------------------------------
// Types
// ----------------------------------------------------------------------

export type StatusFilter = "ok" | "error" | "all";
export type SpanTypeFilter =
  | "llm"
  | "tool"
  | "retrieval"
  | "generic"
  | "all";
export type PeriodFilter = "1h" | "24h" | "7d" | "all";

export interface FilterState {
  status: StatusFilter;
  spanType: SpanTypeFilter;
  period: PeriodFilter;
  failedOnly: boolean;
}

// ----------------------------------------------------------------------
// URL <-> state plumbing
// ----------------------------------------------------------------------

const DEFAULTS: FilterState = {
  status: "all",
  spanType: "all",
  period: "all",
  failedOnly: false,
};

function readFromParams(params: URLSearchParams): FilterState {
  const get = <T extends string>(key: string, allowed: T[]): T | "all" => {
    const v = params.get(key);
    return v && (allowed as string[]).includes(v) ? (v as T) : "all";
  };
  return {
    status: get("status", ["ok", "error"] as const) as StatusFilter,
    spanType: get(
      "span_type",
      ["llm", "tool", "retrieval", "generic"] as const
    ) as SpanTypeFilter,
    period: get("period", ["1h", "24h", "7d"] as const) as PeriodFilter,
    failedOnly: params.get("failed_only") === "true",
  };
}

function writeToParams(
  current: URLSearchParams,
  next: FilterState
): URLSearchParams {
  const out = new URLSearchParams(current.toString());
  if (next.status === "all") out.delete("status");
  else out.set("status", next.status);
  if (next.spanType === "all") out.delete("span_type");
  else out.set("span_type", next.spanType);
  if (next.period === "all") out.delete("period");
  else out.set("period", next.period);
  if (next.failedOnly) out.set("failed_only", "true");
  else out.delete("failed_only");
  return out;
}

// ----------------------------------------------------------------------
// Conversion to API-shaped filters
// ----------------------------------------------------------------------

function periodToSince(period: PeriodFilter): string | undefined {
  if (period === "all") return undefined;
  const ms =
    period === "1h" ? 60 * 60 * 1000
    : period === "24h" ? 24 * 60 * 60 * 1000
    : /* "7d" */ 7 * 24 * 60 * 60 * 1000;
  return new Date(Date.now() - ms).toISOString();
}

/**
 * Convert UI filter state to the stable shape used as queryKey.
 * IMPORTANT: do NOT compute `since` here — that produces a fresh
 * ISO string every render and triggers infinite refetches.
 * The query function calls periodToSince at fetch time instead.
 */
export interface ApiFilterKey {
  status?: "ok" | "error";
  span_type?: "llm" | "tool" | "retrieval" | "generic";
  period?: PeriodFilter; // stable: "1h" not a timestamp
  has_failed_eval?: boolean;
}

export function filtersToApi(state: FilterState): ApiFilterKey {
  return {
    status: state.status === "all" ? undefined : state.status,
    span_type: state.spanType === "all" ? undefined : state.spanType,
    period: state.period === "all" ? undefined : state.period,
    has_failed_eval: state.failedOnly ? true : undefined,
  };
}

/**
 * Resolve a UI filter to the wire-format filters the API client expects.
 * Computes `since` from `period` here, at fetch time.
 */
export function apiFiltersForFetch(key: ApiFilterKey): TraceListFilters {
  return {
    status: key.status,
    span_type: key.span_type,
    since: key.period ? periodToSince(key.period) : undefined,
    has_failed_eval: key.has_failed_eval,
  };
}

// ----------------------------------------------------------------------
// The hook
// ----------------------------------------------------------------------

export function useFilters() {
  const router = useRouter();
  const params = useSearchParams();

  const filters = useMemo<FilterState>(
    () => readFromParams(params ?? new URLSearchParams()),
    [params]
  );

  const setFilters = useCallback(
    (next: Partial<FilterState>) => {
      const merged = { ...filters, ...next };
      const newParams = writeToParams(
        params ?? new URLSearchParams(),
        merged
      );
      const qs = newParams.toString();
      router.replace(qs ? `?${qs}` : "?", { scroll: false });
    },
    [filters, params, router]
  );

  const hasActiveFilters =
    filters.status !== "all" ||
    filters.spanType !== "all" ||
    filters.period !== "all" ||
    filters.failedOnly;

  const resetFilters = useCallback(
    () => router.replace("?", { scroll: false }),
    [router]
  );

  return { filters, setFilters, hasActiveFilters, resetFilters, DEFAULTS };
}