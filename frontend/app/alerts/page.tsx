"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import {
  listAlerts,
  deleteAlert,
  updateAlert,
  listAlertEvents,
  testAlert,
} from "@/lib/api";
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
import type { AlertRuleItem } from "@/lib/types";
import { CreateAlertDialog } from "@/components/alerts/create-alert-dialog";

export default function AlertsPage() {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["alerts"],
    queryFn: () => listAlerts(),
  });

  const { data: eventsData } = useQuery({
    queryKey: ["alert-events"],
    queryFn: () => listAlertEvents(10),
    refetchInterval: 30_000, // refresh every 30s — show recent fires
  });

  const deleteMutation = useMutation({
    mutationFn: (ruleId: string) => deleteAlert(ruleId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });

  const togglePauseMutation = useMutation({
    mutationFn: (params: { ruleId: string; active: boolean }) =>
      updateAlert(params.ruleId, { active: params.active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });

  const testMutation = useMutation({
    mutationFn: (ruleId: string) => testAlert(ruleId),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["alert-events"] });
      if (result.delivered) {
        alert("Test alert delivered successfully.");
      } else {
        alert(`Test alert failed: ${result.error_message ?? "unknown error"}`);
      }
    },
  });

  return (
    <main className="min-h-screen p-8 max-w-6xl mx-auto">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Alerts</h1>
          <p className="text-sm text-gray-500">
            Rules that notify you when something goes wrong
            {data && (
              <span className="ml-2 text-gray-400">
                ({data.items.length}{" "}
                {data.items.length === 1 ? "rule" : "rules"})
              </span>
            )}
          </p>
        </div>
        <CreateAlertDialog />
      </div>

      {/* Recent fires banner */}
      {eventsData && eventsData.items.length > 0 && (
        <RecentFiresBanner events={eventsData.items} />
      )}

      {isLoading && (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      )}

      {error && (
        <div className="text-sm text-red-600 py-8">
          Error loading alerts: {(error as Error).message}
        </div>
      )}

      {data && data.items.length === 0 && (
        <div className="text-center py-12 text-sm text-gray-500">
          <p>No alert rules yet.</p>
          <p className="text-xs text-gray-400 mt-1">
            Create one to get notified when an eval&apos;s pass rate drops or
            traces start erroring.
          </p>
        </div>
      )}

      {data && data.items.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[200px]">Name</TableHead>
              <TableHead className="w-[180px]">Condition</TableHead>
              <TableHead className="w-[140px]">Delivery</TableHead>
              <TableHead className="w-[100px]">Status</TableHead>
              <TableHead className="w-[140px]">Last fired</TableHead>
              <TableHead className="text-right w-[220px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.map((rule) => (
              <AlertRow
                key={rule.id}
                rule={rule}
                onDelete={() => deleteMutation.mutate(rule.id)}
                isDeleting={
                  deleteMutation.isPending &&
                  deleteMutation.variables === rule.id
                }
                onToggleActive={() =>
                  togglePauseMutation.mutate({
                    ruleId: rule.id,
                    active: !rule.active,
                  })
                }
                isToggling={
                  togglePauseMutation.isPending &&
                  togglePauseMutation.variables?.ruleId === rule.id
                }
                onTest={() => testMutation.mutate(rule.id)}
                isTesting={
                  testMutation.isPending &&
                  testMutation.variables === rule.id
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

function AlertRow({
  rule,
  onDelete,
  isDeleting,
  onToggleActive,
  isToggling,
  onTest,
  isTesting,
}: {
  rule: AlertRuleItem;
  onDelete: () => void;
  isDeleting: boolean;
  onToggleActive: () => void;
  isToggling: boolean;
  onTest: () => void;
  isTesting: boolean;
}) {
  const busy = isDeleting || isToggling || isTesting;

  return (
    <TableRow>
      <TableCell className="font-medium text-sm">{rule.name}</TableCell>
      <TableCell>
        <Badge variant="outline">{rule.condition_type}</Badge>
      </TableCell>
      <TableCell>
        <Badge variant="secondary">{rule.delivery_channel}</Badge>
      </TableCell>
      <TableCell>
        {rule.active ? (
          <Badge variant="secondary">active</Badge>
        ) : (
          <Badge variant="outline">paused</Badge>
        )}
      </TableCell>
      <TableCell className="text-xs text-gray-500">
        {rule.last_fired_at ? formatRelativeTime(rule.last_fired_at) : "—"}
      </TableCell>
      <TableCell className="text-right">
        <div className="flex items-center justify-end gap-3 text-xs">
          <button
            onClick={onTest}
            disabled={busy}
            className="text-blue-600 hover:underline disabled:text-gray-400 disabled:no-underline"
            title="Fire this alert immediately to test the delivery channel"
          >
            {isTesting ? "Testing…" : "Test"}
          </button>
          <button
            onClick={onToggleActive}
            disabled={busy}
            className="text-gray-700 hover:underline disabled:text-gray-400 disabled:no-underline"
          >
            {isToggling ? "…" : rule.active ? "Pause" : "Resume"}
          </button>
          <button
            onClick={() => {
              if (confirm(`Delete alert "${rule.name}"?`)) onDelete();
            }}
            disabled={busy}
            className="text-red-600 hover:underline disabled:text-gray-400 disabled:no-underline"
          >
            {isDeleting ? "Deleting…" : "Delete"}
          </button>
        </div>
      </TableCell>
    </TableRow>
  );
}

// ----------------------------------------------------------------------
// Recent fires banner
// ----------------------------------------------------------------------

function RecentFiresBanner({
  events,
}: {
  events: {
    id: string;
    message: string;
    fired_at: string;
    delivered: boolean;
  }[];
}) {
  const latest = events[0];

  return (
    <div className="mb-6 rounded-md border bg-amber-50 border-amber-200 px-4 py-3 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-medium text-amber-900">
            🚨 {events.length} recent{" "}
            {events.length === 1 ? "alert" : "alerts"}
          </div>
          <div className="text-xs text-amber-800 mt-1">
            Latest: &quot;{latest.message}&quot;{" "}
            <span className="text-amber-600">
              · {formatRelativeTime(latest.fired_at)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}