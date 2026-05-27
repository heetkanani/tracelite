import type { SpanItem } from "@/lib/types";

/**
 * A span enriched with its position in the trace tree.
 * Used by the waterfall view to render nested bars.
 */
export interface WaterfallNode {
  span: SpanItem;
  depth: number;          // 0 = root, 1 = child, 2 = grandchild, ...
  startOffsetMs: number;  // ms from the trace's overall start time
  durationMs: number;     // safe duration (0 if missing)
  children: WaterfallNode[];
}

/**
 * Summary stats about the whole tree — needed to size the bars proportionally.
 */
export interface WaterfallStats {
  totalDurationMs: number;  // span of the entire trace, in ms
  traceStartMs: number;     // epoch ms when the trace's earliest span started
}

/**
 * Turn a flat array of spans into a nested tree with computed positions.
 *
 * Handles three tricky cases:
 *  - Orphans: spans whose parent_span_id doesn't exist in this list
 *    (e.g. parent arrived too late and was dropped, or the parent is
 *    in a different trace). We treat them as roots so they still render.
 *  - Missing durations: spans without ended_at get duration 0.
 *  - Multiple roots: a malformed trace may have several roots.
 *    All are rendered at depth 0.
 */
export function buildWaterfall(spans: SpanItem[]): {
  roots: WaterfallNode[];
  stats: WaterfallStats;
} {
  if (spans.length === 0) {
    return { roots: [], stats: { totalDurationMs: 0, traceStartMs: 0 } };
  }

  // Compute the timing window of the whole trace.
  // We use min(started_at) and max(ended_at OR started_at + duration).
  const startTimes = spans.map((s) => new Date(s.started_at).getTime());
  const endTimes = spans.map((s) => {
    if (s.ended_at) return new Date(s.ended_at).getTime();
    const start = new Date(s.started_at).getTime();
    return start + (s.duration_ms ?? 0);
  });
  const traceStartMs = Math.min(...startTimes);
  const traceEndMs = Math.max(...endTimes);
  const totalDurationMs = Math.max(traceEndMs - traceStartMs, 1); // never 0

  // Build a node for each span (no children yet)
  const nodesById = new Map<string, WaterfallNode>();
  for (const span of spans) {
    const startMs = new Date(span.started_at).getTime();
    nodesById.set(span.id, {
      span,
      depth: 0, // filled in later
      startOffsetMs: startMs - traceStartMs,
      durationMs: span.duration_ms ?? 0,
      children: [],
    });
  }

  // Link parent → child. Track which nodes are children of some parent.
  const childIds = new Set<string>();
  for (const node of nodesById.values()) {
    const parentId = node.span.parent_span_id;
    if (parentId && nodesById.has(parentId)) {
      nodesById.get(parentId)!.children.push(node);
      childIds.add(node.span.id);
    }
  }

  // Roots = nodes that are not children of anyone in this list
  // (true roots, plus orphans whose parents are missing)
  const roots: WaterfallNode[] = [];
  for (const node of nodesById.values()) {
    if (!childIds.has(node.span.id)) {
      roots.push(node);
    }
  }

  // Sort siblings by start time so the waterfall flows left-to-right.
  const sortChildren = (node: WaterfallNode) => {
    node.children.sort((a, b) => a.startOffsetMs - b.startOffsetMs);
    node.children.forEach(sortChildren);
  };
  roots.sort((a, b) => a.startOffsetMs - b.startOffsetMs);
  roots.forEach(sortChildren);

  // Walk the tree to assign depth.
  const assignDepth = (node: WaterfallNode, d: number) => {
    node.depth = d;
    node.children.forEach((c) => assignDepth(c, d + 1));
  };
  roots.forEach((r) => assignDepth(r, 0));

  return {
    roots,
    stats: { totalDurationMs, traceStartMs },
  };
}

/**
 * Flatten a tree into a render-ready array (pre-order: parent first, then children).
 * The waterfall renders one row per node, so we just need them in display order.
 */
export function flattenWaterfall(roots: WaterfallNode[]): WaterfallNode[] {
  const out: WaterfallNode[] = [];
  const walk = (node: WaterfallNode) => {
    out.push(node);
    node.children.forEach(walk);
  };
  roots.forEach(walk);
  return out;
}