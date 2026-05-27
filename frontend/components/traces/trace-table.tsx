"use client";

import Link from "next/link";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type { TraceListItem } from "@/lib/types";
import {
  formatCost,
  formatDuration,
  formatRelativeTime,
  formatTraceName,
  shortId,
} from "@/lib/format";

interface TraceTableProps {
  traces: TraceListItem[];
  hasActiveFilters?: boolean;
  onResetFilters?: () => void;
}

export function TraceTable({
  traces,
  hasActiveFilters = false,
  onResetFilters,
}: TraceTableProps) {
  if (traces.length === 0) {
    if (hasActiveFilters) {
      return (
        <div className="text-center py-12">
          <p className="text-sm text-gray-600">No traces match these filters.</p>
          <p className="text-xs text-gray-400 mt-1">
            Try widening the time range or clearing the type/status filters.
          </p>
          {onResetFilters && (
            <button
              onClick={onResetFilters}
              className="mt-3 text-sm text-blue-600 hover:underline"
            >
              Clear all filters
            </button>
          )}
        </div>
      );
    }
    return (
      <div className="text-center py-12 text-sm text-gray-500">
        <p>No traces yet.</p>
        <p className="text-xs text-gray-400 mt-1">
          Run your instrumented app to see traces appear here.
        </p>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[160px]">ID</TableHead>
          <TableHead className="w-[140px]">Started</TableHead>
          <TableHead>Name</TableHead>
          <TableHead className="text-right w-[80px]">Spans</TableHead>
          <TableHead className="text-right w-[100px]">Duration</TableHead>
          <TableHead className="text-right w-[120px]">Cost</TableHead>
          <TableHead className="w-[80px]">Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {traces.map((t) => (
          <TableRow key={t.id} className="hover:bg-gray-50">
            <TableCell className="font-mono text-xs">
              <Link
                href={`/traces/${t.id}`}
                className="text-blue-600 hover:underline"
              >
                {shortId(t.id)}
              </Link>
            </TableCell>
            <TableCell className="text-sm text-gray-600">
              {formatRelativeTime(t.started_at)}
            </TableCell>
            <TableCell className="text-sm">
              {formatTraceName(t.name)}
            </TableCell>
            <TableCell className="text-right text-sm">{t.span_count}</TableCell>
            <TableCell className="text-right text-sm font-mono">
              {formatDuration(t.max_duration_ms)}
            </TableCell>
            <TableCell className="text-right text-sm font-mono">
              {formatCost(t.total_cost_usd)}
            </TableCell>
            <TableCell>
              {t.has_error ? (
                <Badge variant="destructive">error</Badge>
              ) : (
                <Badge variant="secondary">ok</Badge>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}