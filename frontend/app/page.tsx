"use client";

import { useAuth } from "@/lib/auth-context";
import { Dashboard } from "@/components/dashboard";
import Link from "next/link";

export default function Home() {
  const { user } = useAuth();

  // Still bootstrapping — show nothing to avoid flash
  if (user === undefined) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-sm text-gray-400">Loading…</div>
      </div>
    );
  }

  // Logged in → show dashboard
  if (user) {
    return <Dashboard />;
  }

  // Logged out → show landing page
  return <Landing />;
}

function Landing() {
  return (
    <div className="min-h-screen bg-white">
      {/* Hero */}
      <div className="max-w-4xl mx-auto px-8 pt-24 pb-16 text-center">
        <div className="inline-block bg-gray-100 text-gray-600 text-xs font-medium px-3 py-1 rounded-full mb-6">
          Open-source · Self-hosted · Free
        </div>
        <h1 className="text-5xl font-bold text-gray-900 tracking-tight mb-6">
          Observability for your{" "}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-600 to-indigo-600">
            LLM apps
          </span>
        </h1>
        <p className="text-xl text-gray-500 max-w-2xl mx-auto mb-10 leading-relaxed">
          tracelite captures every prompt, response, cost, and latency from your AI
          pipelines — so you can debug faster, evaluate quality, and catch regressions
          before your users do.
        </p>
        <div className="flex items-center justify-center gap-4">
          <Link
            href="/signup"
            className="px-6 py-3 bg-gray-900 text-white rounded-lg font-medium hover:bg-gray-700 transition-colors"
          >
            Get started free
          </Link>
          <Link
            href="/login"
            className="px-6 py-3 text-gray-600 hover:text-gray-900 font-medium transition-colors"
          >
            Sign in →
          </Link>
        </div>
      </div>

      {/* Feature grid */}
      <div className="max-w-5xl mx-auto px-8 pb-24">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {FEATURES.map((f) => (
            <div key={f.title} className="border rounded-xl p-6 bg-white hover:shadow-sm transition-shadow">
              <div className="text-2xl mb-3">{f.icon}</div>
              <h3 className="font-semibold text-gray-900 mb-2">{f.title}</h3>
              <p className="text-sm text-gray-500 leading-relaxed">{f.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* How it works */}
      <div className="bg-gray-50 border-t border-b">
        <div className="max-w-4xl mx-auto px-8 py-20">
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-12">
            Up and running in minutes
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {STEPS.map((s, i) => (
              <div key={s.title} className="text-center">
                <div className="w-8 h-8 bg-gray-900 text-white rounded-full flex items-center justify-center text-sm font-bold mx-auto mb-4">
                  {i + 1}
                </div>
                <h3 className="font-semibold text-gray-900 mb-2">{s.title}</h3>
                <p className="text-sm text-gray-500">{s.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Code snippet */}
      <div className="max-w-3xl mx-auto px-8 py-20">
        <h2 className="text-2xl font-bold text-gray-900 text-center mb-4">
          One API call to start tracing
        </h2>
        <p className="text-center text-gray-500 mb-8">
          Send spans over HTTP — no SDK required.
        </p>
        <div className="bg-gray-950 rounded-xl p-6 text-sm font-mono overflow-x-auto">
          <pre className="text-gray-300 whitespace-pre">{CODE_SNIPPET}</pre>
        </div>
      </div>

      {/* CTA */}
      <div className="bg-gray-900 text-white">
        <div className="max-w-3xl mx-auto px-8 py-16 text-center">
          <h2 className="text-3xl font-bold mb-4">Ready to see inside your AI?</h2>
          <p className="text-gray-400 mb-8">
            Self-host in minutes. Your data never leaves your infrastructure.
          </p>
          <Link
            href="/signup"
            className="inline-block px-8 py-3 bg-white text-gray-900 rounded-lg font-medium hover:bg-gray-100 transition-colors"
          >
            Create free account
          </Link>
        </div>
      </div>

      {/* Footer */}
      <div className="border-t">
        <div className="max-w-5xl mx-auto px-8 py-6 flex items-center justify-between text-sm text-gray-400">
          <span>tracelite — open-source LLM observability</span>
          <div className="flex gap-6">
            <a
              href="https://github.com/your-username/tracelite"
              className="hover:text-gray-600 transition-colors"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub
            </a>
            <Link href="/login" className="hover:text-gray-600 transition-colors">
              Login
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

const FEATURES = [
  {
    icon: "🔍",
    title: "Trace every LLM call",
    description:
      "Capture inputs, outputs, token counts, cost, and latency for every model call in your pipeline — automatically.",
  },
  {
    icon: "✅",
    title: "Automated evaluations",
    description:
      "Define rules (regex, JSON schema, LLM-as-judge) that run on every new trace. Know instantly when quality drops.",
  },
  {
    icon: "🚨",
    title: "Alerts & monitoring",
    description:
      "Get notified when pass rate drops, error rate spikes, or cost per trace exceeds your threshold.",
  },
  {
    icon: "🐛",
    title: "Debug agent loops",
    description:
      "See every tool call, retrieval, and LLM step in a trace. Understand exactly what your agent did and why.",
  },
  {
    icon: "💰",
    title: "Cost tracking",
    description:
      "Track spending per trace, per user, per session. Catch runaway agent loops before they drain your budget.",
  },
  {
    icon: "🔒",
    title: "Self-hosted",
    description:
      "Run entirely on your infrastructure. Your prompts and responses never touch a third-party server.",
  },
];

const STEPS = [
  {
    title: "Deploy with Docker",
    description: "One docker compose up command starts Postgres and the API server.",
  },
  {
    title: "Create an account",
    description: "Sign up, grab your API key from Settings, and you're ready to send data.",
  },
  {
    title: "Send your first trace",
    description: "POST to /v1/spans with your API key. Traces appear in the dashboard instantly.",
  },
];

const CODE_SNIPPET = `import httpx

httpx.post("http://localhost:8000/v1/spans", 
  headers={"X-API-Key": "tl-your-key"},
  json={
    "trace_id": "abc-123",
    "span_type": "llm",
    "model": "gpt-4o",
    "input": [{"role": "user", "content": "Hello!"}],
    "output": "Hi there!",
    "cost_usd": 0.0003,
    "duration_ms": 850,
  }
)`;