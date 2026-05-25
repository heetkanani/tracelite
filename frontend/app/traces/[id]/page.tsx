"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { getTrace } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { SpanCard } from "@/components/traces/span-card";
import {
  formatCost,
  formatDuration,
  formatRelativeTime,
  formatTraceName,
  shortId,
} from "@/lib/format";

export default function TraceDetailPage() {
  const params = useParams<{ id: string }>();
  const traceId = params.id;

  const { data, isLoading, error } = useQuery({
    queryKey: ["trace", traceId],
    queryFn: () => getTrace(traceId),
    enabled: !!traceId,
  });

  // Update the browser tab title to include the trace ID
  useEffect(() => {
    if (traceId) document.title = `Trace ${shortId(traceId)} — tracelite`;
    return () => {
      document.title = "tracelite";
    };
  }, [traceId]);

  return (
    <main className="min-h-screen p-8 max-w-4xl mx-auto">
      {/* Back link */}
      <Link
        href="/"
        className="text-sm text-gray-500 hover:text-gray-900 inline-block mb-6"
      >
        ← Back to traces
      </Link>

      {/* Loading */}
      {isLoading && (
        <div className="space-y-3">
          <Skeleton className="h-8 w-1/3" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-20 w-full mt-6" />
          <Skeleton className="h-20 w-full" />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="border rounded-md bg-white p-6 text-center">
          <h2 className="text-lg font-semibold text-gray-900">Trace not found</h2>
          <p className="text-sm text-gray-500 mt-1">
            It may have been deleted, or the URL may be incorrect.
          </p>
          <p className="text-xs text-gray-400 mt-3 font-mono break-all">
            {(error as Error).message}
          </p>
          <Link
            href="/"
            className="inline-block mt-4 text-sm text-blue-600 hover:underline"
          >
            ← Back to traces
          </Link>
        </div>
      )}

      {/* Loaded */}
      {data && (
        <>
          <TraceHeader trace={data.trace} spanCount={data.spans.length} />

          <h2 className="text-sm font-semibold text-gray-700 mt-8 mb-3">
            Spans ({data.spans.length})
          </h2>

          {data.spans.length === 0 ? (
            <p className="text-sm text-gray-400 py-8 text-center">
              This trace has no spans yet.
            </p>
          ) : (
            <div className="space-y-2">
              {data.spans.map((span) => (
                <SpanCard key={span.id} span={span} />
              ))}
            </div>
          )}
        </>
      )}
    </main>
  );
}

// -----------------------------------------------------------------------
// Sub-components
// -----------------------------------------------------------------------

function TraceHeader({
  trace,
  spanCount,
}: {
  trace: {
    id: string;
    name: string | null;
    started_at: string;
    total_cost_usd: number;
    max_duration_ms: number | null;
    has_error: boolean;
  };
  spanCount: number;
}) {
  return (
    <div>
      <h1 className="text-2xl font-semibold flex items-center gap-3">
        {formatTraceName(trace.name)}
        {trace.has_error && <Badge variant="destructive">error</Badge>}
      </h1>

      <p className="text-xs text-gray-500 font-mono mt-1">
        {trace.id}
      </p>

      <div className="flex gap-6 text-sm text-gray-600 mt-3">
        <Stat label="Started" value={formatRelativeTime(trace.started_at)} />
        <Stat label="Spans" value={String(spanCount)} />
        <Stat label="Duration" value={formatDuration(trace.max_duration_ms)} />
        <Stat label="Cost" value={formatCost(trace.total_cost_usd)} />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-gray-400 uppercase tracking-wide">
        {label}
      </div>
      <div className="font-medium text-gray-900">{value}</div>
    </div>
  );
}