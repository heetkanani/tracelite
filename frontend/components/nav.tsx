"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Traces" },
  { href: "/evaluations", label: "Evaluations" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <nav className="border-b bg-white">
      <div className="max-w-6xl mx-auto px-8 py-3 flex items-center gap-6">
        <Link href="/" className="font-semibold text-gray-900">
          tracelite
        </Link>
        <div className="flex items-center gap-1 text-sm">
          {NAV_ITEMS.map((item) => {
            // "/" matches the homepage exactly; anything else uses startsWith
            // so /traces/<id> highlights "Traces" too.
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
    </nav>
  );
}