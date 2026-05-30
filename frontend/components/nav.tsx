"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

const NAV_ITEMS = [
  { href: "/", label: "Traces" },
  { href: "/evaluations", label: "Evaluations" },
  { href: "/alerts", label: "Alerts" },
  { href: "/settings", label: "Settings" },
];

export function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  async function handleLogout() {
    await logout(); // context handles api call + clearing user
    router.replace("/login");
  }

  return (
    <nav className="border-b bg-white">
      <div className="max-w-6xl mx-auto px-8 py-3 flex items-center justify-between">
        {/* Left: logo + nav links */}
        <div className="flex items-center gap-6">
          <Link href="/" className="font-semibold text-gray-900">
            tracelite
          </Link>
          <div className="flex items-center gap-1 text-sm">
            {NAV_ITEMS.map((item) => {
              const isActive =
                item.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`px-3 py-1.5 rounded-md transition-colors ${
                    isActive
                      ? "bg-gray-100 text-gray-900 font-medium"
                      : "text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>

        {/* Right: auth state */}
        <div className="flex items-center gap-3 text-sm">
          {/* undefined = still bootstrapping → show nothing to avoid flash */}
          {user === undefined && null}

          {/* null = logged out */}
          {user === null && (
            <>
              <Link
                href="/login"
                className="text-gray-600 hover:text-gray-900 px-3 py-1.5 rounded-md hover:bg-gray-50 transition-colors"
              >
                Login
              </Link>
              <Link
                href="/signup"
                className="bg-gray-900 text-white px-3 py-1.5 rounded-md hover:bg-gray-700 transition-colors"
              >
                Sign up
              </Link>
            </>
          )}

          {/* object = logged in */}
          {user && (
            <>
              <span className="text-gray-500 text-xs">{user.email}</span>
              <button
                onClick={handleLogout}
                className="text-gray-600 hover:text-gray-900 px-3 py-1.5 rounded-md hover:bg-gray-50 transition-colors"
              >
                Logout
              </button>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}