"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { listAlertEvents } from "@/lib/api";
import { formatRelativeTime } from "@/lib/format";

const TWENTY_FOUR_HOURS_MS = 24 * 60 * 60 * 1000;

/**
 * Compact alert summary for the homepage.
 *
 * Renders only when there are recent events (last 24h). Otherwise null —
 * no banner taking up space on a healthy system.
 */
export function RecentAlertsWidget() {
  const { data } = useQuery({
    queryKey: ["alert-events"],
    queryFn: () => listAlertEvents(20),
    refetchInterval: 30_000,
  });

  // Lazy initializer runs ONCE at mount — allowed to be impure.
  // The effect below only updates this on a timer, never synchronously.
  const [now, setNow] = useState<number>(() => Date.now());

  useEffect(() => {
    // Re-capture every minute so the 24h window stays accurate
    // for long-lived browser sessions. No sync setState — only callback.
    const interval = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(interval);
  }, []);

  if (!data || data.items.length === 0) {
    return null;
  }

  const cutoff = now - TWENTY_FOUR_HOURS_MS;
  const recent = data.items.filter(
    (e) => new Date(e.fired_at).getTime() >= cutoff
  );

  if (recent.length === 0) return null;

  const latest = recent[0];

  return (
    <div className="mb-6 rounded-md border bg-amber-50 border-amber-200 px-4 py-3 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="font-medium text-amber-900">
            🚨 {recent.length} recent{" "}
            {recent.length === 1 ? "alert" : "alerts"}{" "}
            <span className="font-normal text-amber-700">
              · most recent {formatRelativeTime(latest.fired_at)}
            </span>
          </div>
          <div className="text-xs text-amber-800 mt-1 truncate">
            {latest.message}
          </div>
        </div>
        <Link
          href="/alerts"
          className="text-xs text-amber-900 hover:underline whitespace-nowrap font-medium"
        >
          View all →
        </Link>
      </div>
    </div>
  );
}