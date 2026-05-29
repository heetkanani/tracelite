"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ConditionType, EvalDefinitionItem } from "@/lib/types";

interface ConditionConfigFormProps {
  conditionType: ConditionType;
  config: Record<string, unknown>;
  onConfigChange: (next: Record<string, unknown>) => void;
  // Eval definitions for the eval_id dropdown
  availableEvals?: EvalDefinitionItem[];
}

export function ConditionConfigForm({
  conditionType,
  config,
  onConfigChange,
  availableEvals,
}: ConditionConfigFormProps) {
  const patch = (key: string, value: unknown) => {
    const next = { ...config };
    if (value === "" || value === null || value === undefined) {
      delete next[key];
    } else {
      next[key] = value;
    }
    onConfigChange(next);
  };

  if (conditionType === "eval_pass_rate_below") {
    return (
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="cfg-eval-id">Which eval to watch</Label>
          <Select
            value={(config.eval_id as string | undefined) ?? ""}
            onValueChange={(v) => patch("eval_id", v)}
          >
            <SelectTrigger id="cfg-eval-id">
              <SelectValue placeholder="Pick an eval…" />
            </SelectTrigger>
            <SelectContent>
              {(availableEvals ?? []).map((e) => (
                <SelectItem key={e.id} value={e.id}>
                  {e.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="cfg-threshold">Threshold</Label>
            <Input
              id="cfg-threshold"
              type="number"
              step="0.05"
              min="0"
              max="1"
              value={(config.threshold as number | undefined) ?? ""}
              onChange={(e) =>
                patch(
                  "threshold",
                  e.target.value === "" ? undefined : Number(e.target.value)
                )
              }
              placeholder="0.8"
            />
            <p className="text-[10px] text-gray-500">
              0.0–1.0 (e.g. 0.8 = 80%)
            </p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cfg-window">Window (min)</Label>
            <Input
              id="cfg-window"
              type="number"
              min="1"
              value={(config.window_minutes as number | undefined) ?? ""}
              onChange={(e) =>
                patch(
                  "window_minutes",
                  e.target.value === "" ? undefined : Number(e.target.value)
                )
              }
              placeholder="60"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cfg-min-sample">Min sample</Label>
            <Input
              id="cfg-min-sample"
              type="number"
              min="1"
              value={(config.min_sample_size as number | undefined) ?? ""}
              onChange={(e) =>
                patch(
                  "min_sample_size",
                  e.target.value === "" ? undefined : Number(e.target.value)
                )
              }
              placeholder="5"
            />
            <p className="text-[10px] text-gray-500">Skip if fewer</p>
          </div>
        </div>
      </div>
    );
  }

  // trace_error_rate_above placeholder — we haven't implemented the
  // condition function for it yet; the form is here so the dropdown
  // doesn't crash if someone picks it.
  if (conditionType === "trace_error_rate_above") {
    return (
      <div className="text-xs text-gray-500 rounded-md border bg-gray-50 p-3">
        Condition <strong>trace_error_rate_above</strong> isn&apos;t
        implemented yet. Stay tuned.
      </div>
    );
  }

  return null;
}