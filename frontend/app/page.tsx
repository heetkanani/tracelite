"use client";

import { useInfiniteQuery } from "@tanstack/react-query";

import { listTraces } from "@/lib/api";
import { TraceTable } from "@/components/traces/trace-table";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useFilters, filtersToApi } from "@/lib/filters";
import { FilterBar } from "@/components/traces/filter-bar";
export default function Home() {
  const { filters } = useFilters();
  const apiFilters = filtersToApi(filters);

  const {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ["traces", apiFilters],
    queryFn: ({ pageParam }) =>
      listTraces({ limit: 50, cursor: pageParam, filters: apiFilters }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  });

  // Flatten all pages of results into one array for the table.
  const allTraces = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <main className="min-h-screen p-8 max-w-6xl mx-auto">
      <FilterBar />

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