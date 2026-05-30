"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listApiKeys, createApiKey, deleteApiKey } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { ApiKeyCreated } from "@/lib/types";
import { formatRelativeTime } from "@/lib/format";

export default function SettingsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [newKeyName, setNewKeyName] = useState("");
  const [justCreated, setJustCreated] = useState<ApiKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);

  const { data: keys = [], isLoading } = useQuery({
    queryKey: ["api-keys"],
    queryFn: listApiKeys,
  });

  const createMutation = useMutation({
    mutationFn: (name: string) => createApiKey(name),
    onSuccess: (created) => {
      setJustCreated(created);
      setNewKeyName("");
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteApiKey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  function handleCreate() {
    const name = newKeyName.trim();
    if (!name) return;
    createMutation.mutate(name);
  }

  async function handleCopy(key: string) {
    await navigator.clipboard.writeText(key);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <main className="min-h-screen p-8 max-w-3xl mx-auto">
      <h1 className="text-2xl font-semibold text-gray-900 mb-1">Settings</h1>
      <p className="text-sm text-gray-500 mb-8">
        Manage your account and API keys.
      </p>

      {/* Account info */}
      <section className="mb-10">
        <h2 className="text-sm font-medium text-gray-700 uppercase tracking-wide mb-3">
          Account
        </h2>
        <div className="border rounded-md bg-white p-4 text-sm text-gray-600">
          Logged in as <span className="font-medium text-gray-900">{user?.email}</span>
        </div>
      </section>

      {/* Just-created key banner — shown once */}
      {justCreated && (
        <div className="mb-6 border border-yellow-300 bg-yellow-50 rounded-md p-4">
          <p className="text-sm font-medium text-yellow-800 mb-2">
            ⚠️ Copy your API key now — it wont be shown again.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-white border rounded px-3 py-2 text-xs font-mono break-all">
              {justCreated.key}
            </code>
            <button
              onClick={() => handleCopy(justCreated.key)}
              className="shrink-0 px-3 py-2 text-xs bg-yellow-700 text-white rounded hover:bg-yellow-800 transition-colors"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
          <button
            onClick={() => setJustCreated(null)}
            className="mt-2 text-xs text-yellow-700 hover:underline"
          >
            I have copied it, dismiss
          </button>
        </div>
      )}

      {/* API Keys */}
      <section>
        <h2 className="text-sm font-medium text-gray-700 uppercase tracking-wide mb-3">
          API Keys
        </h2>

        {/* Create new key */}
        <div className="flex gap-2 mb-4">
          <input
            type="text"
            placeholder="Key name (e.g. production, local-dev)"
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            className="flex-1 border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
          />
          <button
            onClick={handleCreate}
            disabled={!newKeyName.trim() || createMutation.isPending}
            className="px-4 py-2 text-sm bg-gray-900 text-white rounded-md hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {createMutation.isPending ? "Creating…" : "Create key"}
          </button>
        </div>

        {/* Key list */}
        {isLoading && (
          <p className="text-sm text-gray-400 py-4 text-center">Loading…</p>
        )}

        {!isLoading && keys.length === 0 && (
          <div className="border rounded-md bg-white p-6 text-center text-sm text-gray-400">
            No API keys yet. Create one above to start sending traces.
          </div>
        )}

        {keys.length > 0 && (
          <div className="border rounded-md bg-white divide-y">
            {keys.map((k) => (
              <div
                key={k.id}
                className="flex items-center justify-between px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-gray-900">{k.name}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Created {formatRelativeTime(k.created_at)}
                    {k.last_used_at && (
                      <> · Last used {formatRelativeTime(k.last_used_at)}</>
                    )}
                  </p>
                </div>
                <button
                  onClick={() => deleteMutation.mutate(k.id)}
                  disabled={deleteMutation.isPending}
                  className="text-xs text-red-500 hover:text-red-700 disabled:opacity-50 transition-colors"
                >
                  Revoke
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}