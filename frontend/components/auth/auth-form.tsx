"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";

// ----------------------------------------------------------------------
// Shared form for both login and signup. The 'mode' prop swaps copy
// and adds the optional name field for signup.
// ----------------------------------------------------------------------

export type AuthFormMode = "login" | "signup";

interface AuthFormProps {
  mode: AuthFormMode;
  onSubmit: (payload: {
    email: string;
    password: string;
    name?: string;
  }) => Promise<void>;
}

export function AuthForm({ mode, onSubmit }: AuthFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    // Client-side guard. Backend will re-check.
    if (mode === "signup" && password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setIsSubmitting(true);
    try {
      await onSubmit({
        email: email.trim(),
        password,
        name: name.trim() || undefined,
      });
      // On success, parent redirects. We don't reset state here in case
      // the parent wants to show success feedback first.
    } catch (e) {
      if (e instanceof ApiError) {
        // Special-case the 422 from Pydantic — its detail is an array.
        // We extract a sensible message instead of dumping JSON.
        if (e.status === 422) {
          setError("Please check your input and try again.");
        } else {
          setError(e.message.includes(":")
            ? e.message.split(":").slice(1).join(":").trim()
            : e.message);
        }
      } else {
        setError("Something went wrong. Try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  const isSignup = mode === "signup";

  return (
    <form onSubmit={handleSubmit} className="space-y-4 w-full max-w-sm">
      {isSignup && (
        <div className="space-y-1.5">
          <Label htmlFor="auth-name">Name (optional)</Label>
          <Input
            id="auth-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Heet Kothari"
            autoComplete="name"
          />
        </div>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="auth-email">Email</Label>
        <Input
          id="auth-email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          autoComplete="email"
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="auth-password">Password</Label>
        <Input
          id="auth-password"
          type="password"
          required
          minLength={isSignup ? 8 : 1}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder={isSignup ? "At least 8 characters" : "Your password"}
          autoComplete={isSignup ? "new-password" : "current-password"}
        />
      </div>

      {error && (
        <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      <Button type="submit" disabled={isSubmitting} className="w-full">
        {isSubmitting
          ? isSignup ? "Creating account…" : "Signing in…"
          : isSignup ? "Sign up" : "Sign in"}
      </Button>
    </form>
  );
}