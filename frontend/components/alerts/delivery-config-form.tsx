"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { DeliveryChannel } from "@/lib/types";

interface DeliveryConfigFormProps {
  deliveryChannel: DeliveryChannel;
  config: Record<string, unknown>;
  onConfigChange: (next: Record<string, unknown>) => void;
}

export function DeliveryConfigForm({
  deliveryChannel,
  config,
  onConfigChange,
}: DeliveryConfigFormProps) {
  const patch = (key: string, value: unknown) => {
    const next = { ...config };
    if (value === "" || value === null || value === undefined) {
      delete next[key];
    } else {
      next[key] = value;
    }
    onConfigChange(next);
  };

  if (deliveryChannel === "log") {
    return (
      <div className="text-xs text-gray-500 rounded-md border bg-gray-50 p-3">
        Alerts will be written to the backend log. No config needed.
      </div>
    );
  }

  if (deliveryChannel === "slack_webhook") {
    return (
      <div className="space-y-1.5">
        <Label htmlFor="cfg-webhook">Slack webhook URL</Label>
        <Input
          id="cfg-webhook"
          value={(config.webhook_url as string | undefined) ?? ""}
          onChange={(e) => patch("webhook_url", e.target.value)}
          placeholder="https://hooks.slack.com/services/..."
          className="font-mono text-xs"
        />
        <p className="text-[11px] text-gray-500">
          Use <code className="font-mono">mock://anything</code> for testing
          without a real Slack workspace.
        </p>
      </div>
    );
  }

  // email — not implemented yet
  return (
    <div className="text-xs text-gray-500 rounded-md border bg-gray-50 p-3">
      Email delivery isnt implemented yet.
    </div>
  );
}