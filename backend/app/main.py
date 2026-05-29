"""
tracelite backend — FastAPI entry point.

Run with: uvicorn app.main:app --reload --port 8000
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.evaluations import start_eval_worker, stop_eval_worker
from app.db import init_pool, close_pool, get_pool
from app.routes.spans import router as spans_router
from app.routes.traces import router as traces_router
from app.routes.evals import router as evals_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    await init_pool()
    print("✅ Database pool initialized")

    await start_eval_worker()
    print("✅ Eval worker started")

    yield  # app runs here

    # --- Shutdown ---
    await stop_eval_worker()
    print("👋 Eval worker stopped")

    await close_pool()
    print("👋 Database pool closed")


app = FastAPI(
    title="tracelite",
    description="Open-source observability for LLM apps",
    version="0.1.0",
    lifespan=lifespan,
)
# CORS: allow the local Next.js dev server to call the API.
# In production we'd lock this down to specific origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount sub-routers
app.include_router(spans_router)
app.include_router(traces_router)
app.include_router(evals_router)

@app.get("/")
async def root():
    """Service info — useful for sanity-checking the server is up."""
    return {"service": "tracelite", "status": "ok", "version": "0.1.0"}


@app.get("/health")
async def health():
    """
    Healthcheck — verifies the server AND the database are reachable.

    This is what load balancers / monitoring tools hit. By including a
    DB ping, we catch the common 'server up but DB broken' failure mode.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # SELECT 1 is the conventional "I'm alive" query
        await conn.fetchval("SELECT 1")
    return {"status": "healthy", "database": "connected"}