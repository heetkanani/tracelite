import type { ReactNode } from "react";

interface JsonBlockProps {
  value: unknown;
  empty?: ReactNode;
}

/**
 * Renders any JSON-compatible value as pretty-printed text inside a
 * scrollable code block. Falls back to `empty` (or "—") when value is null
 * or undefined.
 */
export function JsonBlock({ value, empty }: JsonBlockProps) {
  if (value === null || value === undefined) {
    return (
      <div className="text-xs text-gray-400 italic py-1">
        {empty ?? "—"}
      </div>
    );
  }

  let text: string;
  try {
    text = typeof value === "string"
      ? value
      : JSON.stringify(value, null, 2);
  } catch {
    // circular references, etc.
    text = String(value);
  }

  return (
    <pre className="bg-gray-50 border rounded-md px-3 py-2 text-xs font-mono overflow-x-auto whitespace-pre">
      {text}
    </pre>
  );
}