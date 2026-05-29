"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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

import { createAlert, listEvals } from "@/lib/api";
import type {
  AlertRuleCreatePayload,
  ConditionType,
  DeliveryChannel,
} from "@/lib/types";

import { ConditionConfigForm } from "@/components/alerts/condition-config-form";
import { DeliveryConfigForm } from "@/components/alerts/delivery-config-form";

const CONDITION_TYPES: { value: ConditionType; label: string; hint: string }[] = [
  {
    value: "eval_pass_rate_below",
    label: "Eval pass rate below threshold",
    hint: "Fire when a specific eval's pass rate drops too low",
  },
  {
    value: "trace_error_rate_above",
    label: "Trace error rate above threshold",
    hint: "(not implemented yet)",
  },
];

const DELIVERY_CHANNELS: { value: DeliveryChannel; label: string }[] = [
  { value: "log", label: "Log only (backend stderr)" },
  { value: "slack_webhook", label: "Slack webhook" },
  { value: "email", label: "Email (not implemented)" },
];

export function CreateAlertDialog() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [conditionType, setConditionType] = useState<ConditionType>(
    "eval_pass_rate_below"
  );
  const [conditionConfig, setConditionConfig] = useState<Record<string, unknown>>({});
  const [deliveryChannel, setDeliveryChannel] = useState<DeliveryChannel>("log");
  const [deliveryConfig, setDeliveryConfig] = useState<Record<string, unknown>>(
    {}
  );
  const [minResend, setMinResend] = useState<number>(60);
  const [error, setError] = useState<string | null>(null);

  // Fetch evals so the condition form's eval_id dropdown has options
  const { data: evalsData } = useQuery({
    queryKey: ["evals"],
    queryFn: () => listEvals(),
    enabled: open, // only fetch when dialog opens
  });

  const createMutation = useMutation({
    mutationFn: (payload: AlertRuleCreatePayload) => createAlert(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      resetAndClose();
    },
    onError: (e: Error) => setError(e.message),
  });

  function resetAndClose() {
    setName("");
    setConditionType("eval_pass_rate_below");
    setConditionConfig({});
    setDeliveryChannel("log");
    setDeliveryConfig({});
    setMinResend(60);
    setError(null);
    setOpen(false);
  }

  function handleConditionTypeChange(t: ConditionType) {
    setConditionType(t);
    setConditionConfig({});
  }

  function handleDeliveryChannelChange(c: DeliveryChannel) {
    setDeliveryChannel(c);
    setDeliveryConfig({});
  }

  function handleSubmit() {
    setError(null);
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    if (conditionType === "trace_error_rate_above") {
      setError("This condition type isn't implemented yet");
      return;
    }
    if (deliveryChannel === "email") {
      setError("Email delivery isn't implemented yet");
      return;
    }

    const payload: AlertRuleCreatePayload = {
      name: name.trim(),
      condition_type: conditionType,
      config: conditionConfig,
      delivery_channel: deliveryChannel,
      delivery_config: deliveryConfig,
      active: true,
      min_resend_minutes: minResend,
    };
    createMutation.mutate(payload);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>+ New alert</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>Create alert rule</DialogTitle>
          <DialogDescription>
            Get notified when something crosses a threshold.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Name */}
          <div className="space-y-1.5">
            <Label htmlFor="alert-name">Name</Label>
            <Input
              id="alert-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. LLM relevance dropped"
            />
          </div>

          {/* Condition type */}
          <div className="space-y-1.5">
            <Label htmlFor="alert-condition-type">Condition</Label>
            <Select
              value={conditionType}
              onValueChange={(v) =>
                handleConditionTypeChange(v as ConditionType)
              }
            >
              <SelectTrigger id="alert-condition-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CONDITION_TYPES.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-gray-500">
              {CONDITION_TYPES.find((o) => o.value === conditionType)?.hint}
            </p>
          </div>

          {/* Condition config */}
          <div className="rounded-md border bg-gray-50 p-3">
            <ConditionConfigForm
              conditionType={conditionType}
              config={conditionConfig}
              onConfigChange={setConditionConfig}
              availableEvals={evalsData?.items}
            />
          </div>

          {/* Delivery channel */}
          <div className="space-y-1.5">
            <Label htmlFor="alert-delivery">Deliver via</Label>
            <Select
              value={deliveryChannel}
              onValueChange={(v) =>
                handleDeliveryChannelChange(v as DeliveryChannel)
              }
            >
              <SelectTrigger id="alert-delivery">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DELIVERY_CHANNELS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Delivery config */}
          <div className="rounded-md border bg-gray-50 p-3">
            <DeliveryConfigForm
              deliveryChannel={deliveryChannel}
              config={deliveryConfig}
              onConfigChange={setDeliveryConfig}
            />
          </div>

          {/* Min resend */}
          <div className="space-y-1.5">
            <Label htmlFor="alert-min-resend">
              Don&apos;t re-fire for (minutes)
            </Label>
            <Input
              id="alert-min-resend"
              type="number"
              min="0"
              max="1440"
              value={minResend}
              onChange={(e) => setMinResend(Number(e.target.value) || 0)}
            />
            <p className="text-xs text-gray-500">
              Anti-spam cooldown. 60 = one alert per hour at most while the
              condition stays true.
            </p>
          </div>

          {error && <div className="text-xs text-red-600">{error}</div>}
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