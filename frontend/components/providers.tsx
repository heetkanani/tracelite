"use client";

import { AuthProvider } from "@/lib/auth-context";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

/**
 * Wraps the app in TanStack Query's provider. Marked "use client" because
 * QueryClient holds state — must be created on the client.
 */
export function Providers({ children }: { children: ReactNode }) {
  // useState ensures one QueryClient per app instance, not one per render.
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false, // don't spam the API on every tab switch
            staleTime: 30_000, // consider data fresh for 30s
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}