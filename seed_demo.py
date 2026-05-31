"""
seed_demo.py — Populate tracelite with realistic demo data.

Run from the project root:
    $env:DATABASE_URL="<url>"
    python seed_demo.py

Requirements:
    pip install asyncpg python-dotenv

What it creates:
    - 1 demo user (demo@tracelite.local / demo1234)
    - 1 project with an API key
    - Up to ~45 traces (one per unique question) across the last 7 days
    - 3-5 spans per trace (retrieval / tool / multiple LLM steps)
    - Eval definitions + results
    - 2 alert rules
"""

import asyncio
import json
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://tracelite:tracelite_dev@localhost:5432/tracelite",
)

# ---------------------------------------------------------------
# Realistic demo content
# ---------------------------------------------------------------

MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", "claude-3-5-sonnet-20241022"]

# Each QA pair is unique. One trace per question (no repeats).
QA_PAIRS = [
    # --- Product support ---
    ("How do I reset my password?",
     "Click the 'Forgot password' link on the login page and follow the emailed instructions."),
    ("What is your return policy?",
     "Returns are accepted within 30 days of purchase for a full refund. Contact support with your order number."),
    ("Can I change my subscription plan?",
     "Yes, you can change plans anytime from the Billing section of your account settings."),
    ("How do I export my data?",
     "Go to Settings → Data → Export and choose CSV or JSON."),
    ("Why is my invoice showing the wrong amount?",
     "Invoices reflect usage at the end of each billing cycle. Contact billing if you see a discrepancy."),
    ("How do I add a team member?",
     "Go to Settings → Team → Invite and enter their email address."),
    ("What payment methods do you accept?",
     "We accept Visa, Mastercard, Amex, PayPal, and bank transfers for annual plans."),
    ("How do I cancel my account?",
     "Settings → Billing → Cancel subscription. Your data stays available for 30 days after cancellation."),
    ("Can I get a refund?",
     "Refunds are available within 14 days of charge. Email support@tracelite.io with your account email."),
    ("How do I upgrade to the pro plan?",
     "Settings → Billing → Change Plan → select Pro. Changes take effect immediately."),
    ("Is there a free trial?",
     "Yes, a 14-day free trial with full feature access, no credit card required."),
    ("How do I connect my Slack workspace?",
     "Settings → Integrations → Slack → Connect, then authorize the app."),
    ("What are the API rate limits?",
     "1000 requests/minute on Pro, 100 requests/minute on the free plan."),
    ("How do I enable two-factor authentication?",
     "Settings → Security → Two-Factor Authentication, then scan the QR code with your authenticator app."),
    ("Can I use tracelite with LangChain?",
     "Yes, install the tracelite-langchain package and add the TraceLiteCallbackHandler."),
    ("How do I rotate an API key?",
     "Settings → API Keys → revoke the old key and create a new one. Update your app's environment variable."),
    ("Does tracelite support self-hosting?",
     "Yes, the full stack runs via Docker Compose with one command on your own infrastructure."),
    ("How is my data secured?",
     "Passwords are bcrypt-hashed, sessions use HttpOnly cookies, and self-hosting keeps data on your servers."),
    ("Can I filter traces by user?",
     "Yes, use the user_id filter in the dashboard or pass ?user_id= to the traces API."),
    ("What happens when I hit my plan limit?",
     "Ingestion is throttled and you'll get an alert. Upgrade or wait for the next cycle to resume."),

    # --- Interview preparation ---
    ("Can you share an SDE 2 Amazon interview experience?",
     "A typical SDE 2 Amazon loop has 4-5 rounds: two coding, one system design, and one or two behavioral rounds heavy on Leadership Principles."),
    ("What system design topics are common for SDE 2 interviews?",
     "Expect designs like a URL shortener, rate limiter, news feed, or chat system, focusing on scaling, data models, and trade-offs."),
    ("How should I prepare for Amazon's Leadership Principles?",
     "Prepare 2-3 STAR stories per principle, emphasizing Ownership, Bias for Action, and Customer Obsession with measurable impact."),
    ("What's a good 8-week DSA prep plan?",
     "Weeks 1-2 arrays/strings/hashing, 3-4 trees/graphs, 5-6 DP/recursion, 7-8 mixed mock interviews and review."),
    ("How do I explain my thought process during a coding interview?",
     "State your assumptions, outline a brute-force approach, discuss complexity, then optimize while narrating trade-offs."),
    ("What are common behavioral questions for senior engineers?",
     "Tell me about a conflict with a teammate, a project that failed, a time you influenced without authority, and a tough technical decision."),
    ("How long should I prepare for a FAANG interview?",
     "Most candidates spend 8-12 weeks with consistent daily practice, ramping up mock interviews in the final 3 weeks."),
    ("What's the difference between SDE 1 and SDE 2 expectations?",
     "SDE 2 owns ambiguous problems end-to-end, mentors juniors, and drives design decisions rather than just implementing specs."),
    ("How do I handle a coding question I've never seen?",
     "Break it into smaller subproblems, relate it to a known pattern, and communicate continuously even while stuck."),
    ("What should I ask the interviewer at the end?",
     "Ask about team challenges, how success is measured, on-call expectations, and recent technical decisions they're proud of."),
    ("How important is Big-O in interviews?",
     "Very. You should state time and space complexity for every solution and justify why your optimization improves it."),
    ("Can you review a system design for a rate limiter?",
     "A token-bucket or sliding-window approach with Redis works well; discuss distributed consistency and burst handling."),
    ("What's the best way to do mock interviews?",
     "Use a peer or platform under realistic time pressure, record yourself, and review communication as well as correctness."),
    ("How do I negotiate a software engineer offer?",
     "Get competing offers, focus on total comp (base, equity, sign-on), and let recruiters know you're evaluating options."),
    ("What data structures should I master first?",
     "Arrays, hash maps, stacks/queues, trees, heaps, and graphs cover the majority of interview questions."),
    ("How do I prepare for a behavioral round at Google?",
     "Use Googleyness-aligned stories showing collaboration, dealing with ambiguity, and data-driven decisions."),
    ("What's a strong answer to 'tell me about yourself'?",
     "A 60-90 second arc: current role, a key accomplishment with impact, and why you're excited about this opportunity."),
    ("How do I recover from a bad interview round?",
     "Stay composed, since rounds are scored independently; finish strong and treat each remaining round as a fresh start."),
    ("Should I memorize solutions or understand patterns?",
     "Understand patterns. Memorization breaks on variations; pattern recognition generalizes across new problems."),
    ("How do I demonstrate ownership in interviews?",
     "Describe a project you drove end-to-end, the obstacles you removed, and the measurable outcome you were accountable for."),
    ("What's the STAR method?",
     "Situation, Task, Action, Result — a structure for behavioral answers that keeps stories concise and outcome-focused."),
    ("How many LeetCode problems should I solve?",
     "Quality over quantity: ~150-200 well-understood problems across patterns beats grinding 500 superficially."),
    ("How do I handle system design if I lack production experience?",
     "Study reference architectures, reason from first principles about bottlenecks, and practice articulating trade-offs out loud."),
    ("What's expected in an Amazon bar raiser round?",
     "A senior interviewer outside your team probes depth on Leadership Principles and raises the hiring bar with tougher follow-ups."),
    ("How do I stay calm during interviews?",
     "Practice under timed conditions, prepare a warm-up routine, and reframe nerves as focus rather than threat."),
]

TOOL_NAMES = ["search_knowledge_base", "lookup_order", "fetch_account_info", "send_email", "create_ticket", "web_search", "rerank_results"]
RETRIEVAL_QUERIES = ["password reset flow", "billing FAQ", "team management", "API documentation", "integration guides", "interview rubric", "system design patterns", "leadership principles"]

# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def random_time_in_last_days(days: int) -> datetime:
    offset = random.uniform(0, days * 24 * 3600)
    return now_utc() - timedelta(seconds=offset)

def random_cost(model: str) -> float:
    base = {
        "gpt-4o": 0.005,
        "gpt-4o-mini": 0.0002,
        "gpt-3.5-turbo": 0.0008,
        "claude-3-5-sonnet-20241022": 0.004,
    }.get(model, 0.001)
    return round(base * random.uniform(0.5, 3.0), 6)

def random_duration(min_ms: int, max_ms: int) -> int:
    return random.randint(min_ms, max_ms)

async def _insert_span(conn, *, trace_id, name, span_type, start, duration,
                       input_obj=None, output_obj=None, model=None,
                       input_tokens=None, output_tokens=None, cost=None,
                       status="ok", error_message=None):
    end = start + timedelta(milliseconds=duration)
    await conn.execute(
        """
        INSERT INTO spans
            (id, trace_id, name, span_type, started_at, ended_at, duration_ms,
             model, input, output, input_tokens, output_tokens, cost_usd,
             status, error_message, attributes)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
        """,
        uuid.uuid4(), trace_id, name, span_type, start, end, duration,
        model,
        json.dumps(input_obj) if input_obj is not None else None,
        json.dumps(output_obj) if output_obj is not None else None,
        input_tokens, output_tokens, cost,
        status, error_message, "{}",
    )
    return end

# ---------------------------------------------------------------
# Seed
# ---------------------------------------------------------------

async def seed(conn: asyncpg.Connection) -> None:
    print("🌱 Starting demo seed...")

    # 1. Demo user
    demo_email = "demo@tracelite.local"
    existing_user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", demo_email)
    if existing_user:
        user_id = existing_user["id"]
        print(f"  ✓ Demo user already exists ({demo_email})")
    else:
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
            from app.auth import hash_password as bcrypt_hash
            pw_hash = bcrypt_hash("demo1234")
        except ImportError:
            print("  ⚠ Could not import bcrypt hasher — placeholder hash, login won't work.")
            pw_hash = "PLACEHOLDER"
        row = await conn.fetchrow(
            "INSERT INTO users (email, password_hash, name) VALUES ($1,$2,$3) RETURNING id",
            demo_email, pw_hash, "Demo User",
        )
        user_id = row["id"]
        print(f"  ✓ Created demo user: {demo_email} / demo1234")

    # 2. Project
    existing_project = await conn.fetchrow("SELECT id FROM projects WHERE owner_user_id = $1", user_id)
    if existing_project:
        project_id = existing_project["id"]
        print(f"  ✓ Demo project already exists")
    else:
        row = await conn.fetchrow(
            "INSERT INTO projects (owner_user_id, name) VALUES ($1,$2) RETURNING id",
            user_id, "Demo Project",
        )
        project_id = row["id"]
        print(f"  ✓ Created demo project")

    # 3. API key
    existing_key = await conn.fetchrow(
        "SELECT id FROM api_keys WHERE project_id = $1 AND revoked_at IS NULL", project_id
    )
    if existing_key:
        print(f"  ✓ API key already exists")
    else:
        await conn.execute(
            "INSERT INTO api_keys (project_id, name, key) VALUES ($1,$2,$3) ON CONFLICT (key) DO NOTHING",
            project_id, "demo-key", "tl-demo-key-do-not-use-in-production",
        )
        print(f"  ✓ Created demo API key")

    # 4. Traces + spans
    existing_trace_count = await conn.fetchval("SELECT COUNT(*) FROM traces WHERE project_id = $1", project_id)
    if existing_trace_count > 0:
        print(f"  ✓ Traces already seeded ({existing_trace_count} found), skipping")
    else:
        # Mix: sample from the full pool (support + interview) WITH repeats,
        # so popular questions show up across multiple traces like real traffic.
        NUM_TRACES = 45
        # Guarantee broad coverage: include every unique question at least once,
        # then fill the remainder with random repeats.
        chosen = QA_PAIRS[:]  # one of each first
        while len(chosen) < NUM_TRACES:
            chosen.append(random.choice(QA_PAIRS))
        random.shuffle(chosen)
        chosen = chosen[:NUM_TRACES]
        print(f"  → Seeding {len(chosen)} traces (3-5 spans each)...")
        trace_records = []

        user_ids = ["user_alice", "user_bob", "user_carol", "user_dave", None]
        session_ids = [f"session_{j}" for j in range(1, 10)] + [None]

        for question, answer in chosen:
            trace_id = uuid.uuid4()
            started_at = random_time_in_last_days(7)
            model = random.choice(MODELS)
            has_error = random.random() < 0.08

            # Insert the trace FIRST — spans have a FK to traces.
            await conn.execute(
                """
                INSERT INTO traces (id, project_id, name, user_id, session_id, started_at, ended_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
                """,
                trace_id, project_id, question[:60],
                random.choice(user_ids), random.choice(session_ids),
                started_at, started_at,
            )

            # Build a span plan of 3-5 spans:
            # always: retrieval + (1-2 tool) + (1-2 LLM steps)
            n_tools = random.randint(1, 2)
            n_llm = random.randint(1, 2)
            # ensure total in 3-5: retrieval(1) + tools + llm
            total = 1 + n_tools + n_llm
            while total > 5:
                if n_tools > 1:
                    n_tools -= 1
                elif n_llm > 1:
                    n_llm -= 1
                total = 1 + n_tools + n_llm
            while total < 3:
                n_llm += 1
                total = 1 + n_tools + n_llm

            cursor = started_at
            # retrieval
            q = random.choice(RETRIEVAL_QUERIES)
            d = random_duration(50, 300)
            cursor = await _insert_span(
                conn, trace_id=trace_id, name=f"retrieve: {q}", span_type="retrieval",
                start=cursor, duration=d,
                input_obj={"query": q},
                output_obj={"chunks": random.randint(2, 8), "top_score": round(random.uniform(0.7, 0.99), 2)},
            )

            # tools
            for _ in range(n_tools):
                tname = random.choice(TOOL_NAMES)
                d = random_duration(100, 600)
                cursor = await _insert_span(
                    conn, trace_id=trace_id, name=tname, span_type="tool",
                    start=cursor, duration=d,
                    input_obj={"tool": tname, "args": {}},
                    output_obj={"result": "ok", "records": random.randint(0, 5)},
                )

            # llm steps — last one carries the final answer + possible error
            final_output = None
            last_span_id = None
            for i in range(n_llm):
                is_last = (i == n_llm - 1)
                d = random_duration(400, 2500)
                cost = random_cost(model)
                err = has_error and is_last
                out_content = None if err else (answer if is_last else "intermediate reasoning step")
                end = cursor + timedelta(milliseconds=d)
                span_id = uuid.uuid4()
                await conn.execute(
                    """
                    INSERT INTO spans
                        (id, trace_id, name, span_type, started_at, ended_at, duration_ms,
                         model, input, output, input_tokens, output_tokens, cost_usd,
                         status, error_message, attributes)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                    """,
                    span_id, trace_id,
                    f"chat: {model}", "llm",
                    cursor, end, d, model,
                    json.dumps([{"role": "user", "content": question}]),
                    json.dumps(out_content) if out_content else None,
                    random.randint(80, 400), random.randint(40, 200), cost,
                    "error" if err else "ok",
                    "OpenAI API timeout" if err else None,
                    "{}",
                )
                cursor = end
                if is_last:
                    final_output = out_content
                    last_span_id = span_id

            # Update ended_at now that all spans are placed.
            await conn.execute(
                "UPDATE traces SET ended_at = $1 WHERE id = $2",
                cursor, trace_id,
            )
            trace_records.append((trace_id, last_span_id, has_error, final_output))

        print(f"  ✓ Seeded {len(trace_records)} traces")

        # 5. Eval definitions + results (on the final LLM span of each trace)
        print("  → Seeding eval definitions...")
        eval_def_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO eval_definitions
                (id, project_id, name, evaluator_type, config, applies_to_span_type, active)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            """,
            eval_def_id, project_id, "No hallucination marker", "substring_absent",
            json.dumps({"text": "I don't know"}), "llm", True,
        )
        eval_def_id_2 = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO eval_definitions
                (id, project_id, name, evaluator_type, config, applies_to_span_type, active)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            """,
            eval_def_id_2, project_id, "Response not empty", "regex_match",
            json.dumps({"pattern": ".+"}), "llm", True,
        )

        print("  → Seeding eval results...")
        for trace_id, span_id, has_error, final_output in trace_records:
            if span_id is None:
                continue
            passed1 = bool(final_output) and "I don't know" not in final_output
            await conn.execute(
                "INSERT INTO eval_results (span_id, eval_id, passed, score, reasoning) VALUES ($1,$2,$3,$4,$5)",
                span_id, eval_def_id, passed1, 1.0 if passed1 else 0.0,
                "substring not found" if passed1 else "substring present or no output",
            )
            passed2 = bool(final_output)
            await conn.execute(
                "INSERT INTO eval_results (span_id, eval_id, passed, score, reasoning) VALUES ($1,$2,$3,$4,$5)",
                span_id, eval_def_id_2, passed2, 1.0 if passed2 else 0.0,
                "pattern matched" if passed2 else "no output to match",
            )
        print("  ✓ Seeded eval definitions and results")

        # 6. Alert rules
        print("  → Seeding alert rules...")
        await conn.execute(
            "INSERT INTO alert_rules (project_id, name, condition_type, config, active) VALUES ($1,$2,$3,$4,$5)",
            project_id, "Pass rate dropped", "eval_pass_rate_below",
            json.dumps({"threshold_pct": 80, "window_minutes": 60}), True,
        )
        await conn.execute(
            "INSERT INTO alert_rules (project_id, name, condition_type, config, active) VALUES ($1,$2,$3,$4,$5)",
            project_id, "High error rate", "trace_error_rate_above",
            json.dumps({"threshold_pct": 10, "window_minutes": 60}), True,
        )
        print("  ✓ Seeded 2 alert rules")

    print()
    print("✅ Demo seed complete!")
    print()
    print("   Login:    demo@tracelite.local / demo1234")


async def main() -> None:
    print(f"Connecting to: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await seed(conn)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())