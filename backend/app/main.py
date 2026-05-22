"""
tracelite backend — FastAPI entry point.

Run with: uvicorn app.main:app --reload --port 8000
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db import init_pool, close_pool, get_pool
from app.routes.spans import router as spans_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage the database pool's lifecycle alongside the app's.

    - On startup: open the asyncpg pool.
    - On shutdown: close it cleanly so no connections leak.
    """
    # Startup
    await init_pool()
    print("✅ Database pool initialized")
    yield
    # Shutdown
    await close_pool()
    print("👋 Database pool closed")


app = FastAPI(
    title="tracelite",
    description="Open-source observability for LLM apps",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount sub-routers
app.include_router(spans_router)

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