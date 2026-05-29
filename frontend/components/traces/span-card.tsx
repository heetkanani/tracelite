"use client";

import { Badge } from "@/components/ui/badge";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { JsonBlock } from "@/components/traces/json-block";
import type { EvalResultItem, SpanItem } from "@/lib/types";
import { formatCost, formatDuration } from "@/lib/format";

export function SpanCard({
  span,
  evalResults,
}: {
  span: SpanItem;
  evalResults?: EvalResultItem[];
}) {
  // Show input/output sections only for spans that could meaningfully have them
  const hasIO = span.input !== undefined || span.output !== undefined;

  return (
    <div className="border rounded-md bg-white">
      {/* Header row */}
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <div className="flex items-center gap-2 min-w-0">
          <SpanTypeBadge type={span.span_type} />
          <span className="font-medium text-sm truncate">{span.name}</span>
          {span.status === "error" && (
            <Badge variant="destructive">error</Badge>
          )}
        </div>
        <div className="flex items-center gap-4 text-xs text-gray-500 font-mono shrink-0">
          {span.cost_usd != null && span.cost_usd > 0 && (
            <span>{formatCost(span.cost_usd)}</span>
          )}
          <span>{formatDuration(span.duration_ms)}</span>
        </div>
      </div>

      {/* Metadata row */}
      <div className="px-4 py-2 text-xs text-gray-600 flex flex-wrap gap-x-4 gap-y-1">
        {span.model && <Meta label="Model" value={span.model} mono />}
        {span.input_tokens != null && span.output_tokens != null && (
          <Meta
            label="Tokens"
            value={`${span.input_tokens} in / ${span.output_tokens} out`}
          />
        )}
        {span.parent_span_id && (
          <Meta
            label="Parent"
            value={span.parent_span_id.slice(0, 8)}
            mono
          />
        )}
      </div>

      {/* Eval result badges (only when present) */}
      {evalResults && evalResults.length > 0 && (
        <div className="px-4 pb-2 flex flex-wrap items-center gap-1.5">
          {evalResults.map((result) => (
            <EvalBadge key={result.result_id} result={result} />
          ))}
        </div>
      )}

      {/* Error message */}
      {span.error_message && (
        <div className="px-4 py-2 border-t bg-red-50 text-xs text-red-700 font-mono">
          {span.error_message}
        </div>
      )}

      {/* Input / Output (collapsible) */}
      {hasIO && (
        <>
          <CollapsibleSection title="Input">
            <JsonBlock value={span.input} empty="No input captured" />
          </CollapsibleSection>
          <CollapsibleSection title="Output">
            <JsonBlock value={span.output} empty="No output captured" />
          </CollapsibleSection>
        </>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------
// Sub-components
// -----------------------------------------------------------------------

function SpanTypeBadge({ type }: { type: SpanItem["span_type"] }) {
  const variant =
    type === "llm" ? "default"
    : type === "tool" ? "secondary"
    : "outline";
  return <Badge variant={variant}>{type}</Badge>;
}

function Meta({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <span>
      <span className="text-gray-400">{label}:</span>{" "}
      <span className={mono ? "font-mono" : ""}>{value}</span>
    </span>
  );
}

function EvalBadge({ result }: { result: EvalResultItem }) {
  // Three states based on passed: pass / fail / skipped
  const isPass = result.passed === true;
  const isFail = result.passed === false;

  const icon = isPass ? "✓" : isFail ? "✗" : "⊘";
  const colorClasses = isPass
    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
    : isFail
    ? "bg-red-50 text-red-700 border-red-200"
    : "bg-gray-50 text-gray-600 border-gray-200";

  // Tooltip text — score, reasoning if present
  const tooltipParts: string[] = [];
  if (result.score !== null) {
    tooltipParts.push(`Score: ${result.score.toFixed(2)}`);
  }
  if (result.reasoning) {
    tooltipParts.push(result.reasoning);
  }
  const tooltip = tooltipParts.join(" · ") || result.eval_name;

  return (
    <span
      title={tooltip}
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border ${colorClasses}`}
    >
      <span className="font-mono">{icon}</span>
      <span className="truncate max-w-[180px]">{result.eval_name}</span>
    </span>
  );
}