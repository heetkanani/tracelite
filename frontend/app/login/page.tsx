"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthForm } from "@/components/auth/auth-form";
import { useAuth } from "@/lib/auth-context";

const DEMO_EMAIL = "demo@tracelite.local";
const DEMO_PASSWORD = "demo1234";

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated, isLoading } = useAuth();
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoError, setDemoError] = useState("");

  // If already logged in, bounce to home.
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace("/");
    }
  }, [isLoading, isAuthenticated, router]);

  async function handleLogin(payload: { email: string; password: string }) {
    await login(payload);
    router.replace("/");
  }

  async function handleDemoLogin() {
    setDemoError("");
    setDemoLoading(true);
    try {
      await login({ email: DEMO_EMAIL, password: DEMO_PASSWORD });
      router.replace("/");
    } catch {
      setDemoError("Demo login failed — the server may be waking up. Try again in ~30s.");
    } finally {
      setDemoLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-8">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center space-y-1">
          <h1 className="text-2xl font-semibold">Welcome back</h1>
          <p className="text-sm text-gray-500">Sign in to your account</p>
        </div>

        {/* Demo access box */}
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm">
          <p className="font-medium text-blue-900 mb-2">👋 Just exploring?</p>
          <p className="text-blue-800 mb-3">
            Use the demo account to browse a dashboard with sample traces, evals,
            and alerts — no signup needed.
          </p>
          <div className="font-mono text-xs text-blue-900 bg-white rounded border border-blue-200 px-3 py-2 mb-3 space-y-0.5">
            <div>email: {DEMO_EMAIL}</div>
            <div>password: {DEMO_PASSWORD}</div>
          </div>
          <button
            onClick={handleDemoLogin}
            disabled={demoLoading}
            className="w-full bg-blue-600 text-white rounded-md py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-60 transition-colors"
          >
            {demoLoading ? "Signing in…" : "Sign in as demo user"}
          </button>
          {demoError && (
            <p className="text-xs text-red-600 mt-2">{demoError}</p>
          )}
        </div>

        <AuthForm mode="login" onSubmit={handleLogin} />

        <p className="text-center text-sm text-gray-500">
          Don&apos;t have an account?{" "}
          <Link href="/signup" className="text-blue-600 hover:underline">
            Sign up
          </Link>
        </p>
      </div>
    </main>
  );
}