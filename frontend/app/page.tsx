"use client";

import { useInfiniteQuery } from "@tanstack/react-query";

import { listTraces } from "@/lib/api";
import { TraceTable } from "@/components/traces/trace-table";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

export default function Home() {
  const {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ["traces"],
    queryFn: ({ pageParam }) =>
      listTraces({ limit: 50, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  });

  // Flatten all pages of results into one array for the table.
  const allTraces = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <main className="min-h-screen p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold">tracelite</h1>
        <p className="text-sm text-gray-500">
          Recent traces
          {data && (
            <span className="ml-2 text-gray-400">
              ({allTraces.length} loaded)
            </span>
          )}
        </p>
      </div>

      {isLoading && (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      )}

      {error && (
        <div className="text-sm text-red-600 py-8">
          Error loading traces: {(error as Error).message}
        </div>
      )}

      {data && <TraceTable traces={allTraces} />}

      {hasNextPage && (
        <div className="mt-6 text-center">
          <Button
            variant="outline"
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? "Loading…" : "Load more"}
          </Button>
        </div>
      )}

      {data && !hasNextPage && (
        <div className="mt-6 text-center text-xs text-gray-400">
          End of results.
        </div>
      )}
    </main>
  );
}