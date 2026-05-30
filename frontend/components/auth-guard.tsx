"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

const PUBLIC_ROUTES = ["/login", "/signup"];

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const isPublicRoute = PUBLIC_ROUTES.includes(pathname);

  useEffect(() => {
    // Still bootstrapping — wait until we know the auth state
    if (user === undefined) return;

    if (!isPublicRoute && user === null) {
      // Trying to visit a protected page while logged out → go to login
      router.replace("/login");
    }

    if (isPublicRoute && user !== null) {
      // Already logged in, visiting login/signup → go to dashboard
      router.replace("/");
    }
  }, [user, isPublicRoute, router]);

  // While bootstrapping on a protected route, show nothing (avoids flash of content)
  if (user === undefined && !isPublicRoute) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-sm text-gray-400">Loading…</div>
      </div>
    );
  }

  // While bootstrapping on a public route (login/signup), render normally
  // so the form is visible immediately
  return <>{children}</>;
}