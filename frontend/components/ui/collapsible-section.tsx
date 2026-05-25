"use client";

import { useState, type ReactNode } from "react";

interface CollapsibleSectionProps {
  title: string;
  defaultOpen?: boolean;
  children: ReactNode;
}

/**
 * Tiny collapsible: a clickable header that toggles its content.
 * Used for input/output JSON viewers and similar reveal-on-demand UI.
 */
export function CollapsibleSection({
  title,
  defaultOpen = false,
  children,
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border-t">
      <button
        onClick={() => setIsOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-4 py-2 text-xs text-gray-600 hover:bg-gray-50 text-left"
      >
        <span className="text-gray-400 inline-block w-2 text-center">
          {isOpen ? "▼" : "▶"}
        </span>
        <span className="font-medium">{title}</span>
      </button>
      {isOpen && <div className="px-4 pb-3">{children}</div>}
    </div>
  );
}