"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { listEvals, deleteEval, runEval, updateEval } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatRelativeTime } from "@/lib/format";
import type { EvalDefinitionItem, EvalRunSummary } from "@/lib/types";
import { CreateEvalDialog } from "@/components/evaluations/create-eval-dialog";

export default function EvaluationsPage() {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["evals"],
    queryFn: () => listEvals(),
  });

  // ----- Mutations: delete, run, toggle active -----

  const deleteMutation = useMutation({
    mutationFn: (evalId: string) => deleteEval(evalId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["evals"] }),
  });

  const [lastRunSummary, setLastRunSummary] = useState<{
    name: string;
    summary: EvalRunSummary;
  } | null>(null);

  const runMutation = useMutation({
    mutationFn: (params: { evalId: string; name: string }) =>
      runEval(params.evalId).then((summary) => ({
        name: params.name,
        summary,
      })),
    onSuccess: (result) => {
      setLastRunSummary(result);
      // Eval results changed; future trace-detail pages will need refetches.
      queryClient.invalidateQueries({ queryKey: ["evals"] });
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: (params: { evalId: string; active: boolean }) =>
      updateEval(params.evalId, { active: params.active }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["evals"] }),
  });

  return (
    <main className="min-h-screen p-8 max-w-6xl mx-auto">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Evaluations</h1>
          <p className="text-sm text-gray-500">
            Rules that automatically score your spans
            {data && (
              <span className="ml-2 text-gray-400">
                ({data.items.length}{" "}
                {data.items.length === 1 ? "eval" : "evals"})
              </span>
            )}
          </p>
        </div>
        <CreateEvalDialog />
      </div>

      {/* Last run summary banner */}
      {lastRunSummary && (
        <div className="mb-4 rounded-md border bg-blue-50 px-4 py-3 text-sm">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="font-medium text-gray-900">
                Ran &quot;{lastRunSummary.name}&quot;
              </div>
              <div className="text-xs text-gray-600 mt-1">
                Evaluated{" "}
                <strong>{lastRunSummary.summary.evaluated}</strong> spans:{" "}
                {lastRunSummary.summary.passed} passed,{" "}
                {lastRunSummary.summary.failed} failed,{" "}
                {lastRunSummary.summary.skipped} skipped. Cost:{" "}
                ${lastRunSummary.summary.total_cost_usd.toFixed(6)}
              </div>
            </div>
            <button
              onClick={() => setLastRunSummary(null)}
              className="text-xs text-gray-400 hover:text-gray-700"
            >
              dismiss
            </button>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      )}

      {error && (
        <div className="text-sm text-red-600 py-8">
          Error loading evals: {(error as Error).message}
        </div>
      )}

      {data && data.items.length === 0 && (
        <div className="text-center py-12 text-sm text-gray-500">
          <p>No evaluations yet.</p>
          <p className="text-xs text-gray-400 mt-1">
            Click &quot;New eval&quot; to create your first rule.
          </p>
        </div>
      )}

      {data && data.items.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[200px]">Name</TableHead>
              <TableHead className="w-[140px]">Type</TableHead>
              <TableHead className="w-[120px]">Applies to</TableHead>
              <TableHead className="w-[100px]">Status</TableHead>
              <TableHead className="w-[140px]">Updated</TableHead>
              <TableHead className="text-right w-[240px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.map((evalDef) => (
              <EvalRow
                key={evalDef.id}
                evalDef={evalDef}
                onDelete={() => deleteMutation.mutate(evalDef.id)}
                isDeleting={
                  deleteMutation.isPending &&
                  deleteMutation.variables === evalDef.id
                }
                onRun={() =>
                  runMutation.mutate({
                    evalId: evalDef.id,
                    name: evalDef.name,
                  })
                }
                isRunning={
                  runMutation.isPending &&
                  runMutation.variables?.evalId === evalDef.id
                }
                onToggleActive={() =>
                  toggleActiveMutation.mutate({
                    evalId: evalDef.id,
                    active: !evalDef.active,
                  })
                }
                isToggling={
                  toggleActiveMutation.isPending &&
                  toggleActiveMutation.variables?.evalId === evalDef.id
                }
              />
            ))}
          </TableBody>
        </Table>
      )}
    </main>
  );
}

// ----------------------------------------------------------------------
// One row
// ----------------------------------------------------------------------

function EvalRow({
  evalDef,
  onDelete,
  isDeleting,
  onRun,
  isRunning,
  onToggleActive,
  isToggling,
}: {
  evalDef: EvalDefinitionItem;
  onDelete: () => void;
  isDeleting: boolean;
  onRun: () => void;
  isRunning: boolean;
  onToggleActive: () => void;
  isToggling: boolean;
}) {
  const anyBusy = isDeleting || isRunning || isToggling;

  return (
    <TableRow>
      <TableCell className="font-medium text-sm">{evalDef.name}</TableCell>
      <TableCell>
        <Badge variant="outline">{evalDef.evaluator_type}</Badge>
      </TableCell>
      <TableCell className="text-sm text-gray-600">
        {evalDef.applies_to_span_type ?? "any"}
      </TableCell>
      <TableCell>
        {evalDef.active ? (
          <Badge variant="secondary">active</Badge>
        ) : (
          <Badge variant="outline">paused</Badge>
        )}
      </TableCell>
      <TableCell className="text-xs text-gray-500">
        {formatRelativeTime(evalDef.updated_at)}
      </TableCell>
      <TableCell className="text-right">
        <div className="flex items-center justify-end gap-3 text-xs">
          <button
            onClick={onRun}
            disabled={anyBusy || !evalDef.active}
            className="text-blue-600 hover:underline disabled:text-gray-400 disabled:no-underline"
            title={
              !evalDef.active
                ? "Resume the eval to run it"
                : "Run this eval against the last 100 spans"
            }
          >
            {isRunning ? "Running…" : "Run now"}
          </button>
          <button
            onClick={onToggleActive}
            disabled={anyBusy}
            className="text-gray-700 hover:underline disabled:text-gray-400 disabled:no-underline"
          >
            {isToggling
              ? "…"
              : evalDef.active
              ? "Pause"
              : "Resume"}
          </button>
          <button
            onClick={() => {
              if (confirm(`Delete eval "${evalDef.name}"?`)) onDelete();
            }}
            disabled={anyBusy}
            className="text-red-600 hover:underline disabled:text-gray-400 disabled:no-underline"
          >
            {isDeleting ? "Deleting…" : "Delete"}
          </button>
        </div>
      </TableCell>
    </TableRow>
  );
}