"use client";

import { useState } from "react";

import type { EvalResultItem, SpanItem } from "@/lib/types";
import {
  buildWaterfall,
  flattenWaterfall,
  niceTicks,
  rollupEvalStatus,
  type WaterfallNode,
  type WaterfallStats,
} from "@/lib/waterfall";
import { formatCost, formatDuration } from "@/lib/format";
import { SpanCard } from "@/components/traces/span-card";

interface WaterfallViewProps {
  spans: SpanItem[];
  evalResultsBySpan?: Map<string, EvalResultItem[]>;
}

export function WaterfallView({
  spans,
  evalResultsBySpan,
}: WaterfallViewProps) {
  // Track which span IDs the user has clicked to expand inline.
  // Set<string> for O(1) lookups; toggle by adding/removing entries.
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  if (spans.length === 0) {
    return (
      <div className="text-center py-12 text-sm text-gray-400">
        No spans in this trace.
      </div>
    );
  }

  const { roots, stats } = buildWaterfall(spans);
  const rows = flattenWaterfall(roots);

  return (
    <div className="border rounded-md bg-white overflow-hidden">
      {/* Header row */}
      <div className="grid grid-cols-[minmax(220px,1fr)_2fr_auto] items-center px-4 py-2 border-b text-xs font-medium text-gray-500 uppercase tracking-wide gap-4">
        <span>Name</span>
        <span>Timeline ({formatDuration(stats.totalDurationMs)})</span>
        <span className="text-right w-[120px]">Duration · Cost</span>
      </div>

      {/* Time axis */}
      <div className="grid grid-cols-[minmax(220px,1fr)_2fr_auto] items-end px-4 pt-2 pb-1 border-b gap-4">
        <span />
        <TimeAxis stats={stats} />
        <span className="w-[120px]" />
      </div>

      {rows.map((node, index) => (
        <WaterfallRow
          key={node.span.id}
          node={node}
          stats={stats}
          showTooltipBelow={index < 2}
          isExpanded={expandedIds.has(node.span.id)}
          onToggle={() => toggleExpanded(node.span.id)}
          evalResults={evalResultsBySpan?.get(node.span.id)}
        />
      ))}
    </div>
  );
}

// ----------------------------------------------------------------------
// One row
// ----------------------------------------------------------------------

function WaterfallRow({
  node,
  stats,
  showTooltipBelow,
  isExpanded,
  onToggle,
  evalResults,
}: {
  node: WaterfallNode;
  stats: WaterfallStats;
  showTooltipBelow: boolean;
  isExpanded: boolean;
  onToggle: () => void;
  evalResults?: EvalResultItem[];
}) {
  const { span, depth, startOffsetMs, durationMs } = node;

  const leftPct = (startOffsetMs / stats.totalDurationMs) * 100;
  const widthPct = Math.max(
    (durationMs / stats.totalDurationMs) * 100,
    0.5
  );

  const isError = span.status === "error";
  const barColor = isError ? "bg-red-500" : colorForSpanType(span.span_type);

  return (
    <>
      <div
        onClick={onToggle}
        className={`grid grid-cols-[minmax(220px,1fr)_2fr_auto] items-center px-4 py-2 border-b last:border-b-0 hover:bg-gray-50 gap-4 text-sm cursor-pointer ${
          isExpanded ? "bg-blue-50/40" : ""
        }`}
      >
        {/* Name + indentation + chevron */}
        <div
          className="flex items-center gap-2 min-w-0"
          style={{ paddingLeft: `${depth * 16}px` }}
        >
          <span className="text-gray-400 text-xs inline-block w-3">
            {isExpanded ? "▼" : "▶"}
          </span>
          <SpanTypeDot type={span.span_type} isError={isError} />
          <span className="truncate text-gray-900">{span.name}</span>
          <EvalStatusIndicator status={rollupEvalStatus(evalResults)} />
        </div>

        {/* Timeline track */}
        <div className="relative h-5 group">
          <div className="absolute inset-0 bg-gray-100 rounded" />
          <div
            className={`absolute top-0 bottom-0 ${barColor} rounded`}
            style={{
              left: `${leftPct}%`,
              width: `${widthPct}%`,
            }}
          />
          <SpanTooltip node={node} showBelow={showTooltipBelow} />
        </div>

        {/* Duration + cost */}
        <div className="text-xs text-gray-600 font-mono text-right w-[120px] shrink-0">
          <div>{formatDuration(durationMs)}</div>
          {span.cost_usd != null && span.cost_usd > 0 && (
            <div className="text-gray-400">{formatCost(span.cost_usd)}</div>
          )}
        </div>
      </div>

      {/* Inline detail panel — only when expanded */}
      {isExpanded && (
        <div
          className="px-4 py-3 border-b last:border-b-0 bg-gray-50"
          style={{ paddingLeft: `${16 + depth * 16}px` }}
        >
          <SpanCard span={span} evalResults={evalResults} />
        </div>
      )}
    </>
  );
}

// ----------------------------------------------------------------------
// Utilities
// ----------------------------------------------------------------------

function colorForSpanType(type: SpanItem["span_type"]): string {
  switch (type) {
    case "llm":
      return "bg-blue-500";
    case "retrieval":
      return "bg-emerald-500";
    case "tool":
      return "bg-amber-500";
    case "generic":
    default:
      return "bg-slate-400";
  }
}

function SpanTypeDot({
  type,
  isError,
}: {
  type: SpanItem["span_type"];
  isError: boolean;
}) {
  const cls = isError ? "bg-red-500" : colorForSpanType(type);
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${cls}`}
      aria-hidden
    />
  );
}

function SpanTooltip({
  node,
  showBelow,
}: {
  node: WaterfallNode;
  showBelow: boolean;
}) {
  const { span, startOffsetMs, durationMs } = node;
  const positionClass = showBelow ? "top-7" : "bottom-7";
  return (
    <div
      className={`absolute z-50 left-0 ${positionClass} hidden group-hover:block pointer-events-none`}
    >
      <div className="bg-gray-900 text-white text-xs rounded-md px-3 py-2 shadow-lg whitespace-nowrap">
        <div className="font-semibold">{span.name}</div>
        <div className="text-gray-300 mt-1 space-y-0.5">
          <div>
            <span className="text-gray-500">Type:</span> {span.span_type}
          </div>
          <div>
            <span className="text-gray-500">Started at:</span>{" "}
            +{Math.round(startOffsetMs)}ms
          </div>
          <div>
            <span className="text-gray-500">Duration:</span>{" "}
            {Math.round(durationMs)}ms
          </div>
          {span.model && (
            <div>
              <span className="text-gray-500">Model:</span> {span.model}
            </div>
          )}
          {span.input_tokens != null && span.output_tokens != null && (
            <div>
              <span className="text-gray-500">Tokens:</span> {span.input_tokens}{" "}
              in / {span.output_tokens} out
            </div>
          )}
          {span.cost_usd != null && span.cost_usd > 0 && (
            <div>
              <span className="text-gray-500">Cost:</span>{" "}
              {formatCost(span.cost_usd)}
            </div>
          )}
          {span.status === "error" && span.error_message && (
            <div className="text-red-300 mt-1">{span.error_message}</div>
          )}
        </div>
      </div>
    </div>
  );
}

function TimeAxis({ stats }: { stats: WaterfallStats }) {
  const ticks = niceTicks(stats.totalDurationMs);
  return (
    <div className="relative h-4">
      {ticks.map((tickMs) => {
        const leftPct = (tickMs / stats.totalDurationMs) * 100;
        return (
          <div
            key={tickMs}
            className="absolute top-0 -translate-x-1/2 text-[10px] text-gray-400 font-mono"
            style={{ left: `${leftPct}%` }}
          >
            {tickMs}ms
          </div>
        );
      })}
    </div>
  );
}

function EvalStatusIndicator({
  status,
}: {
  status: "pass" | "fail" | "none";
}) {
  if (status === "none") return null;
  if (status === "pass") {
    return (
      <span
        title="All evals passed"
        className="text-emerald-600 text-xs font-mono shrink-0"
        aria-label="all evals passed"
      >
        ✓
      </span>
    );
  }
  return (
    <span
      title="One or more evals failed"
      className="text-red-600 text-xs font-mono shrink-0"
      aria-label="eval failed"
    >
      ✗
    </span>
  );
}