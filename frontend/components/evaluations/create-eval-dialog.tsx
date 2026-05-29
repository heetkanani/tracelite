"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ConfigForm } from "@/components/evaluations/config-form";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { createEval } from "@/lib/api";
import type {
  EvalDefinitionCreatePayload,
  EvaluatorType,
  SpanType,
} from "@/lib/types";

// ----------------------------------------------------------------------
// Option configs — same pattern as the trace filter bar
// ----------------------------------------------------------------------

const EVALUATOR_TYPES: { value: EvaluatorType; label: string; hint: string }[] = [
  {
    value: "substring_absent",
    label: "Substring absent",
    hint: "Pass when a given text does NOT appear in the output",
  },
  {
    value: "regex_match",
    label: "Regex match",
    hint: "Pass when a regex pattern matches the output",
  },
  {
    value: "json_schema",
    label: "JSON schema",
    hint: "Validate the output's top-level type and required keys",
  },
  {
    value: "llm_judge",
    label: "LLM as judge",
    hint: "Ask another LLM to score the output (costs $)",
  },
];

const SPAN_TYPE_OPTIONS: { value: SpanType | "any"; label: string }[] = [
  { value: "any", label: "Any span type" },
  { value: "llm", label: "LLM only" },
  { value: "tool", label: "Tool only" },
  { value: "retrieval", label: "Retrieval only" },
  { value: "generic", label: "Generic only" },
];

// ----------------------------------------------------------------------
// The dialog
// ----------------------------------------------------------------------

export function CreateEvalDialog() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [evaluatorType, setEvaluatorType] = useState<EvaluatorType>("substring_absent");
  const [appliesTo, setAppliesTo] = useState<SpanType | "any">("any");
  const [config, setConfig] = useState<Record<string, unknown>>({});

  // When the user switches evaluator types, reset the config so old fields
    // (e.g. substring_absent's "text") don't accidentally leak into the new
    // evaluator's config (e.g. regex_match's "pattern").
    function handleTypeChange(newType: EvaluatorType) {
    setEvaluatorType(newType);
    setConfig({});
    }
  // Submission error
  const [error, setError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: (payload: EvalDefinitionCreatePayload) => createEval(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["evals"] });
      resetAndClose();
    },
    onError: (e: Error) => {
      setError(e.message);
    },
  });

  function resetAndClose() {
    setName("");
    setEvaluatorType("substring_absent");
    setAppliesTo("any");
    setConfig({});
    setError(null);
    setOpen(false);
  }

  function handleSubmit() {
    setError(null);

    if (!name.trim()) {
      setError("Name is required");
      return;
    }

    // Config will be filled in by per-type sub-forms in 6.3c.iii.
    // For now, send an empty config — backend will store it; evaluator
    // functions will report "missing config" until the user edits the
    // eval to fill it in (which we don't support yet — that's 6.3 polish).
    const payload: EvalDefinitionCreatePayload = {
      name: name.trim(),
      evaluator_type: evaluatorType,
      config: config,
      applies_to_span_type: appliesTo === "any" ? null : appliesTo,
      active: true,
    };

    createMutation.mutate(payload);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>+ New eval</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Create evaluation</DialogTitle>
          <DialogDescription>
            Define a rule that scores spans as they arrive.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Name */}
          <div className="space-y-1.5">
            <Label htmlFor="eval-name">Name</Label>
            <Input
              id="eval-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Reject refusal phrases"
            />
          </div>

          {/* Evaluator type */}
          <div className="space-y-1.5">
            <Label htmlFor="eval-type">Evaluator type</Label>
            <Select
              value={evaluatorType}
              onValueChange={(v) => handleTypeChange(v as EvaluatorType)}
            >
              <SelectTrigger id="eval-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {EVALUATOR_TYPES.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-gray-500">
              {EVALUATOR_TYPES.find((o) => o.value === evaluatorType)?.hint}
            </p>
          </div>

          {/* Applies to */}
          <div className="space-y-1.5">
            <Label htmlFor="eval-applies-to">Apply to</Label>
            <Select
              value={appliesTo}
              onValueChange={(v) => setAppliesTo(v as SpanType | "any")}
            >
              <SelectTrigger id="eval-applies-to">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SPAN_TYPE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

            {/* Per-type config fields */}
            <div className="rounded-md border bg-gray-50 p-3">
            <ConfigForm
                evaluatorType={evaluatorType}
                config={config}
                onConfigChange={setConfig}
            />
            </div>

          {/* Error message */}
          {error && (
            <div className="text-xs text-red-600">{error}</div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={resetAndClose}
            disabled={createMutation.isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={createMutation.isPending}
          >
            {createMutation.isPending ? "Creating…" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}