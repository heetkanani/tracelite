"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { EvaluatorType } from "@/lib/types";

interface ConfigFormProps {
  evaluatorType: EvaluatorType;
  config: Record<string, unknown>;
  onConfigChange: (next: Record<string, unknown>) => void;
}

/**
 * Renders the type-specific config fields for the chosen evaluator.
 *
 * State lives in the parent (the dialog); this component is "controlled".
 * onConfigChange is called with the full new config object whenever any
 * field changes, so the parent always has the latest snapshot ready to
 * submit.
 */
export function ConfigForm({
  evaluatorType,
  config,
  onConfigChange,
}: ConfigFormProps) {
  // Helper: patch one field on the config object
  const patch = (key: string, value: unknown) => {
    const next = { ...config };
    if (value === "" || value === null || value === undefined) {
      delete next[key];
    } else {
      next[key] = value;
    }
    onConfigChange(next);
  };

  switch (evaluatorType) {
    case "substring_absent":
      return <SubstringAbsentForm config={config} patch={patch} />;
    case "regex_match":
      return <RegexMatchForm config={config} patch={patch} />;
    case "json_schema":
      return <JsonSchemaForm config={config} patch={patch} />;
    case "llm_judge":
      return <LlmJudgeForm config={config} patch={patch} />;
    default:
      return null;
  }
}

// ----------------------------------------------------------------------
// substring_absent
// ----------------------------------------------------------------------

function SubstringAbsentForm({
  config,
  patch,
}: {
  config: Record<string, unknown>;
  patch: (key: string, value: unknown) => void;
}) {
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label htmlFor="cfg-text">Banned text</Label>
        <Input
          id="cfg-text"
          value={(config.text as string | undefined) ?? ""}
          onChange={(e) => patch("text", e.target.value)}
          placeholder="e.g. I don't know"
        />
        <p className="text-xs text-gray-500">
          The eval fails if this text appears in the span&apos;s output.
        </p>
      </div>
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="cfg-case-sensitive"
          checked={(config.case_sensitive as boolean | undefined) ?? false}
          onChange={(e) => patch("case_sensitive", e.target.checked)}
          className="h-4 w-4"
        />
        <Label htmlFor="cfg-case-sensitive" className="text-sm font-normal">
          Case sensitive
        </Label>
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------
// regex_match
// ----------------------------------------------------------------------

function RegexMatchForm({
  config,
  patch,
}: {
  config: Record<string, unknown>;
  patch: (key: string, value: unknown) => void;
}) {
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label htmlFor="cfg-pattern">Regex pattern</Label>
        <Input
          id="cfg-pattern"
          value={(config.pattern as string | undefined) ?? ""}
          onChange={(e) => patch("pattern", e.target.value)}
          placeholder="e.g. ^Answer:"
          className="font-mono text-sm"
        />
        <p className="text-xs text-gray-500">
          Passes when the pattern matches anywhere in the output.
        </p>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="cfg-flags">Flags (optional)</Label>
        <Input
          id="cfg-flags"
          value={(config.flags as string | undefined) ?? ""}
          onChange={(e) => patch("flags", e.target.value)}
          placeholder="e.g. im (case-insensitive + multiline)"
          className="font-mono text-sm"
        />
        <p className="text-xs text-gray-500">
          Combine letters: i = case-insensitive, m = multiline, s = dotall.
        </p>
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------
// json_schema
// ----------------------------------------------------------------------

const JSON_TYPES = ["object", "array", "string", "number", "boolean", "null"];

function JsonSchemaForm({
  config,
  patch,
}: {
  config: Record<string, unknown>;
  patch: (key: string, value: unknown) => void;
}) {
  const currentType = (config.type as string | undefined) ?? "any";
  const requiredKeys = config.required_keys as string[] | undefined;
  const requiredKeysCsv = requiredKeys?.join(", ") ?? "";

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label htmlFor="cfg-type">Expected top-level type</Label>
        <Select
          value={currentType}
          onValueChange={(v) =>
            patch("type", v === "any" ? undefined : v)
          }
        >
          <SelectTrigger id="cfg-type">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="any">Any (skip type check)</SelectItem>
            {JSON_TYPES.map((t) => (
              <SelectItem key={t} value={t}>
                {t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="cfg-required-keys">
          Required keys (comma-separated, optional)
        </Label>
        <Input
          id="cfg-required-keys"
          value={requiredKeysCsv}
          onChange={(e) => {
            const list = e.target.value
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean);
            patch("required_keys", list.length ? list : undefined);
          }}
          placeholder="e.g. answer, sources"
          className="font-mono text-sm"
        />
        <p className="text-xs text-gray-500">
          Only meaningful for objects. Leave empty to skip this check.
        </p>
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------
// llm_judge
// ----------------------------------------------------------------------

function LlmJudgeForm({
  config,
  patch,
}: {
  config: Record<string, unknown>;
  patch: (key: string, value: unknown) => void;
}) {
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label htmlFor="cfg-prompt">Judge prompt (optional)</Label>
        <Textarea
          id="cfg-prompt"
          value={(config.prompt as string | undefined) ?? ""}
          onChange={(e) => patch("prompt", e.target.value)}
          placeholder="Leave blank to use the default relevance rubric"
          rows={4}
          className="text-sm font-mono"
        />
        <p className="text-xs text-gray-500">
          The judge expects JSON output:{" "}
          <code>{"{\"score\": <1-N>, \"reasoning\": \"...\"}"}</code>
        </p>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="cfg-model">Model</Label>
          <Input
            id="cfg-model"
            value={(config.model as string | undefined) ?? ""}
            onChange={(e) => patch("model", e.target.value)}
            placeholder="gpt-4o-mini"
            className="font-mono text-sm"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="cfg-max-score">Max score</Label>
          <Input
            id="cfg-max-score"
            type="number"
            value={(config.max_score as number | undefined) ?? ""}
            onChange={(e) =>
              patch(
                "max_score",
                e.target.value === "" ? undefined : Number(e.target.value)
              )
            }
            placeholder="5"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="cfg-min-pass">Min pass</Label>
          <Input
            id="cfg-min-pass"
            type="number"
            value={(config.min_pass as number | undefined) ?? ""}
            onChange={(e) =>
              patch(
                "min_pass",
                e.target.value === "" ? undefined : Number(e.target.value)
              )
            }
            placeholder="3"
          />
        </div>
      </div>
    </div>
  );
}