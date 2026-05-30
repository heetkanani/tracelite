"""
seed_demo.py — Populate tracelite with realistic demo data.

Run from the project root:
    python seed_demo.py

Requirements:
    pip install asyncpg python-dotenv

What it creates:
    - 1 demo user (demo@tracelite.local / demo1234)
    - 1 project with an API key
    - 40 traces across the last 7 days
    - 80+ spans (LLM, tool, retrieval)
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

USER_QUESTIONS = [
    "How do I reset my password?",
    "What is your return policy?",
    "Can I change my subscription plan?",
    "How do I export my data?",
    "Why is my invoice showing the wrong amount?",
    "How do I add a team member?",
    "What payment methods do you accept?",
    "How do I cancel my account?",
    "Can I get a refund?",
    "How do I upgrade to the pro plan?",
    "Is there a free trial?",
    "How do I connect my Slack workspace?",
    "What are the API rate limits?",
    "How do I enable two-factor authentication?",
    "Can I use tracelite with LangChain?",
]

ASSISTANT_RESPONSES = [
    "To reset your password, click the 'Forgot password' link on the login page and follow the instructions sent to your email.",
    "Our return policy allows returns within 30 days of purchase for a full refund. Please contact support with your order number.",
    "You can change your subscription plan at any time from the Billing section in your account settings.",
    "To export your data, go to Settings → Data → Export and choose your preferred format (CSV or JSON).",
    "Invoices are generated based on your usage at the end of each billing cycle. If you see a discrepancy, please contact our billing team.",
    "To add a team member, go to Settings → Team → Invite and enter their email address.",
    "We accept all major credit cards (Visa, Mastercard, Amex) as well as PayPal and bank transfers for annual plans.",
    "You can cancel your account from Settings → Billing → Cancel subscription. Your data will be available for 30 days after cancellation.",
    "Refunds are available within 14 days of charge. Please contact support@tracelite.io with your account email.",
    "To upgrade, go to Settings → Billing → Change Plan and select the Pro plan. Changes take effect immediately.",
    "Yes! We offer a 14-day free trial with full access to all features. No credit card required.",
    "To connect Slack, go to Settings → Integrations → Slack and click Connect. You'll be redirected to authorize the app.",
    "The API rate limit is 1000 requests per minute on the Pro plan and 100 requests per minute on the free plan.",
    "To enable 2FA, go to Settings → Security → Two-Factor Authentication and scan the QR code with your authenticator app.",
    "Yes, tracelite has a LangChain integration. Install the tracelite-langchain package and add the TraceLiteCallbackHandler.",
]

TOOL_NAMES = ["search_knowledge_base", "lookup_order", "fetch_account_info", "send_email", "create_ticket"]
RETRIEVAL_QUERIES = ["password reset flow", "billing FAQ", "team management", "API documentation", "integration guides"]

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

# ---------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------

async def seed(conn: asyncpg.Connection) -> None:
    print("🌱 Starting demo seed...")

    # ----------------------------------------------------------
    # 1. Demo user
    # ----------------------------------------------------------
    demo_email = "demo@tracelite.local"
    existing_user = await conn.fetchrow(
        "SELECT id FROM users WHERE email = $1", demo_email
    )

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
            print("  ⚠ Could not import bcrypt hasher — using placeholder hash.")
            print("    The demo user won't be able to log in.")
            pw_hash = "PLACEHOLDER"

        user_row = await conn.fetchrow(
            """
            INSERT INTO users (email, password_hash, name)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            demo_email, pw_hash, "Demo User",
        )
        user_id = user_row["id"]
        print(f"  ✓ Created demo user: {demo_email} / demo1234")

    # ----------------------------------------------------------
    # 2. Demo project
    # ----------------------------------------------------------
    existing_project = await conn.fetchrow(
        "SELECT id FROM projects WHERE owner_user_id = $1", user_id
    )

    if existing_project:
        project_id = existing_project["id"]
        print(f"  ✓ Demo project already exists (id: {project_id})")
    else:
        project_row = await conn.fetchrow(
            """
            INSERT INTO projects (owner_user_id, name)
            VALUES ($1, $2)
            RETURNING id
            """,
            user_id, "Demo Project",
        )
        project_id = project_row["id"]
        print(f"  ✓ Created demo project: Demo Project")

    # ----------------------------------------------------------
    # 3. API key
    # ----------------------------------------------------------
    existing_key = await conn.fetchrow(
        "SELECT id FROM api_keys WHERE project_id = $1 AND revoked_at IS NULL",
        project_id,
    )

    if existing_key:
        print(f"  ✓ API key already exists")
    else:
        demo_key = "tl-demo-key-do-not-use-in-production"
        await conn.execute(
            """
            INSERT INTO api_keys (project_id, name, key)
            VALUES ($1, $2, $3)
            ON CONFLICT (key) DO NOTHING
            """,
            project_id, "demo-key", demo_key,
        )
        print(f"  ✓ Created demo API key: {demo_key}")

    # ----------------------------------------------------------
    # 4. Traces + spans
    # ----------------------------------------------------------
    existing_trace_count = await conn.fetchval(
        "SELECT COUNT(*) FROM traces WHERE project_id = $1", project_id
    )

    if existing_trace_count > 0:
        print(f"  ✓ Traces already seeded ({existing_trace_count} found), skipping")
    else:
        print("  → Seeding 40 traces with spans...")
        trace_ids = []

        for i in range(40):
            trace_id = uuid.uuid4()
            started_at = random_time_in_last_days(7)
            question = random.choice(USER_QUESTIONS)
            answer = random.choice(ASSISTANT_RESPONSES)
            model = random.choice(MODELS)
            has_error = random.random() < 0.08
            has_tool = random.random() < 0.4
            has_retrieval = random.random() < 0.35

            total_duration = random_duration(800, 4000)
            ended_at = started_at + timedelta(milliseconds=total_duration)

            user_ids = ["user_alice", "user_bob", "user_carol", "user_dave", None]
            session_ids = [f"session_{j}" for j in range(1, 8)] + [None]

            await conn.execute(
                """
                INSERT INTO traces (id, project_id, name, user_id, session_id, started_at, ended_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                trace_id, project_id, question[:60],
                random.choice(user_ids), random.choice(session_ids),
                started_at, ended_at,
            )

            span_offset = 0

            if has_retrieval:
                retrieval_duration = random_duration(50, 300)
                retrieval_start = started_at + timedelta(milliseconds=span_offset)
                retrieval_end = retrieval_start + timedelta(milliseconds=retrieval_duration)
                span_offset += retrieval_duration
                q = random.choice(RETRIEVAL_QUERIES)
                await conn.execute(
                    """
                    INSERT INTO spans
                        (id, trace_id, name, span_type, started_at, ended_at, duration_ms,
                         input, output, status, attributes)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                    """,
                    uuid.uuid4(), trace_id,
                    f"retrieve: {q}", "retrieval",
                    retrieval_start, retrieval_end, retrieval_duration,
                    json.dumps({"query": q}),
                    json.dumps({"chunks": random.randint(2, 8), "top_score": round(random.uniform(0.7, 0.99), 2)}),
                    "ok", "{}",
                )

            if has_tool:
                tool_duration = random_duration(100, 600)
                tool_start = started_at + timedelta(milliseconds=span_offset)
                tool_end = tool_start + timedelta(milliseconds=tool_duration)
                span_offset += tool_duration
                tool_name = random.choice(TOOL_NAMES)
                await conn.execute(
                    """
                    INSERT INTO spans
                        (id, trace_id, name, span_type, started_at, ended_at, duration_ms,
                         input, output, status, attributes)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                    """,
                    uuid.uuid4(), trace_id,
                    tool_name, "tool",
                    tool_start, tool_end, tool_duration,
                    json.dumps({"tool": tool_name, "args": {}}),
                    json.dumps({"result": "ok", "records": random.randint(0, 5)}),
                    "ok", "{}",
                )

            llm_duration = max(100, total_duration - span_offset)
            llm_start = started_at + timedelta(milliseconds=span_offset)
            llm_end = ended_at
            cost = random_cost(model)
            input_tokens = random.randint(80, 400)
            output_tokens = random.randint(40, 200)
            status = "error" if has_error else "ok"
            error_msg = "OpenAI API timeout" if has_error else None
            output_content = None if has_error else answer

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
                llm_start, llm_end, llm_duration,
                model,
                json.dumps([{"role": "user", "content": question}]),
                json.dumps(output_content) if output_content else None,
                input_tokens, output_tokens, cost,
                status, error_msg, "{}",
            )
            trace_ids.append((trace_id, span_id, has_error, output_content))

        print(f"  ✓ Seeded 40 traces")

        # ----------------------------------------------------------
        # 5. Eval definitions + results
        # ----------------------------------------------------------
        print("  → Seeding eval definitions...")

        eval_def_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO eval_definitions
                (id, project_id, name, evaluator_type, config, applies_to_span_type, active)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            eval_def_id, project_id,
            "No hallucination marker", "substring_absent",
            json.dumps({"text": "I don't know"}),
            "llm", True,
        )

        eval_def_id_2 = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO eval_definitions
                (id, project_id, name, evaluator_type, config, applies_to_span_type, active)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            eval_def_id_2, project_id,
            "Response not empty", "regex_match",
            json.dumps({"pattern": ".+"}),
            "llm", True,
        )

        print("  → Seeding eval results...")
        for trace_id, span_id, has_error, output_content in trace_ids:
            passed1 = bool(output_content) and "I don't know" not in output_content
            await conn.execute(
                """
                INSERT INTO eval_results (span_id, eval_id, passed, score, reasoning)
                VALUES ($1, $2, $3, $4, $5)
                """,
                span_id, eval_def_id,
                passed1,
                1.0 if passed1 else 0.0,
                "substring not found" if passed1 else "substring present or no output",
            )

            passed2 = bool(output_content)
            await conn.execute(
                """
                INSERT INTO eval_results (span_id, eval_id, passed, score, reasoning)
                VALUES ($1, $2, $3, $4, $5)
                """,
                span_id, eval_def_id_2,
                passed2,
                1.0 if passed2 else 0.0,
                "pattern matched" if passed2 else "no output to match",
            )

        print("  ✓ Seeded eval definitions and results")

        # ----------------------------------------------------------
        # 6. Alert rules
        # ----------------------------------------------------------
        print("  → Seeding alert rules...")

        await conn.execute(
            """
            INSERT INTO alert_rules (project_id, name, condition_type, config, active)
            VALUES ($1, $2, $3, $4, $5)
            """,
            project_id,
            "Pass rate dropped",
            "eval_pass_rate_below",
            json.dumps({"threshold_pct": 80, "window_minutes": 60}),
            True,
        )

        await conn.execute(
            """
            INSERT INTO alert_rules (project_id, name, condition_type, config, active)
            VALUES ($1, $2, $3, $4, $5)
            """,
            project_id,
            "High error rate",
            "trace_error_rate_above",
            json.dumps({"threshold_pct": 10, "window_minutes": 60}),
            True,
        )

        print("  ✓ Seeded 2 alert rules")

    print()
    print("✅ Demo seed complete!")
    print()
    print("   Login:    http://localhost:3000/login")
    print("   Email:    demo@tracelite.local")
    print("   Password: demo1234")
    print()
    print("   Or use the API key: tl-demo-key-do-not-use-in-production")


async def main() -> None:
    print(f"Connecting to: {DATABASE_URL}")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await seed(conn)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())