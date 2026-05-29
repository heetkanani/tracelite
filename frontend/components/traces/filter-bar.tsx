"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import {
  useFilters,
  type PeriodFilter,
  type SpanTypeFilter,
  type StatusFilter,
} from "@/lib/filters";

// ----------------------------------------------------------------------
// Option configs — declared once, referenced by each dropdown.
// ----------------------------------------------------------------------

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All statuses" },
  { value: "ok", label: "OK only" },
  { value: "error", label: "Errors only" },
];

const SPAN_TYPE_OPTIONS: { value: SpanTypeFilter; label: string }[] = [
  { value: "all", label: "All types" },
  { value: "llm", label: "LLM" },
  { value: "tool", label: "Tool" },
  { value: "retrieval", label: "Retrieval" },
  { value: "generic", label: "Generic" },
];

const PERIOD_OPTIONS: { value: PeriodFilter; label: string }[] = [
  { value: "all", label: "All time" },
  { value: "1h", label: "Last 1 hour" },
  { value: "24h", label: "Last 24 hours" },
  { value: "7d", label: "Last 7 days" },
];

// ----------------------------------------------------------------------
// Filter bar
// ----------------------------------------------------------------------

export function FilterBar() {
  const { filters, setFilters, hasActiveFilters, resetFilters } = useFilters();

  return (
    <div className="flex flex-wrap items-center gap-2 mb-6">
      <FilterSelect
        label="Status"
        value={filters.status}
        options={STATUS_OPTIONS}
        onChange={(v) => setFilters({ status: v as StatusFilter })}
      />
      <FilterSelect
        label="Type"
        value={filters.spanType}
        options={SPAN_TYPE_OPTIONS}
        onChange={(v) => setFilters({ spanType: v as SpanTypeFilter })}
      />
      <FilterSelect
        label="Time"
        value={filters.period}
        options={PERIOD_OPTIONS}
        onChange={(v) => setFilters({ period: v as PeriodFilter })}
      />

      {/* Failed-evals toggle */}
      <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer ml-2 h-9 px-3 rounded-md border bg-white">
        <input
          type="checkbox"
          checked={filters.failedOnly}
          onChange={(e) => setFilters({ failedOnly: e.target.checked })}
          className="h-4 w-4 rounded border-gray-300 cursor-pointer"
        />
        <span>Failed evals only</span>
      </label>

      {hasActiveFilters && (
        <Button
          variant="ghost"
          size="sm"
          onClick={resetFilters}
          className="ml-auto text-gray-600"
        >
          Reset filters
        </Button>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------
// One generic dropdown
// ----------------------------------------------------------------------

interface FilterSelectProps<T extends string> {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}

function FilterSelect<T extends string>({
  label,
  value,
  options,
  onChange,
}: FilterSelectProps<T>) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as T)}>
      <SelectTrigger className="w-[180px] h-9 text-sm">
        <span className="text-gray-500 mr-1">{label}:</span>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {options.map((opt) => (
          <SelectItem key={opt.value} value={opt.value}>
            {opt.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}