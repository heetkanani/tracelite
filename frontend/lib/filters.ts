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
}

// ----------------------------------------------------------------------
// URL <-> state plumbing
// ----------------------------------------------------------------------

const DEFAULTS: FilterState = {
  status: "all",
  spanType: "all",
  period: "all",
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

export function filtersToApi(state: FilterState): TraceListFilters {
  return {
    status: state.status === "all" ? undefined : state.status,
    span_type: state.spanType === "all" ? undefined : state.spanType,
    since: periodToSince(state.period),
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
    filters.period !== "all";

  const resetFilters = useCallback(
    () => router.replace("?", { scroll: false }),
    [router]
  );

  return { filters, setFilters, hasActiveFilters, resetFilters, DEFAULTS };
}