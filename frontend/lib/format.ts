/**
 * Display formatting helpers for the dashboard.
 *
 * All functions safely handle null/undefined input by returning "—".
 */

/** ISO timestamp → relative time like "2 min ago". */
export function formatRelativeTime(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  const diffSec = (Date.now() - date.getTime()) / 1000;

  if (diffSec < 5) return "just now";
  if (diffSec < 60) return `${Math.floor(diffSec)}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
}

/** Cost in USD → human-readable. Sub-cent costs show extra decimals. */
export function formatCost(usd: number | null | undefined): string {
  if (usd == null) return "—";
  if (usd === 0) return "$0";
  if (usd < 0.0001) return `$${usd.toFixed(6)}`;
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

/** Duration in ms → "12ms" / "1.2s" / "—". */
export function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

/** Trace name fallback. */
export function formatTraceName(name: string | null): string {
  return name && name.trim().length > 0 ? name : "(unnamed)";
}

/** UUID → short prefix (first 8 chars) for display. */
export function shortId(id: string): string {
  return id.slice(0, 8);
}