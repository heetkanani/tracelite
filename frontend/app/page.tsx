"use client";

import { useInfiniteQuery } from "@tanstack/react-query";

import { listTraces } from "@/lib/api";
import { TraceTable } from "@/components/traces/trace-table";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useFilters, filtersToApi, apiFiltersForFetch } from "@/lib/filters";
import { FilterBar } from "@/components/traces/filter-bar";

export default function Home() {
  const { filters, hasActiveFilters, resetFilters } = useFilters();
  const apiFilters = filtersToApi(filters);

  const {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isFetching,
  } = useInfiniteQuery({
    queryKey: ["traces", apiFilters],
    queryFn: ({ pageParam }) =>
  listTraces({
    limit: 50,
    cursor: pageParam,
    filters: apiFiltersForFetch(apiFilters),
  }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    refetchInterval: 5000,
    refetchOnWindowFocus: true,
  });

  // Flatten all pages of results into one array for the table.
  const allTraces = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <main className="min-h-screen p-8 max-w-6xl mx-auto">
      <div className="mb-8 flex items-center justify-between">
        <div>
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
        <LiveIndicator active={isFetching && !isFetchingNextPage} />
      </div>

      <FilterBar />

      {/* Show skeleton only on the very first load when we have no data yet */}
      {isLoading && !data && (
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

      {data && (
        <div className={isFetching && !isFetchingNextPage ? "opacity-60 transition-opacity" : ""}>
          <TraceTable
            traces={allTraces}
            hasActiveFilters={hasActiveFilters}
            onResetFilters={resetFilters}
          />
        </div>
      )}
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

function LiveIndicator({ active }: { active: boolean }) {
  return (
    <div className="flex items-center gap-2 text-xs text-gray-500">
      <span
        className={`inline-block h-2 w-2 rounded-full ${
          active ? "bg-green-500 animate-pulse" : "bg-gray-300"
        }`}
        aria-hidden
      />
      <span>{active ? "Updating…" : "Live"}</span>
    </div>
  );
}