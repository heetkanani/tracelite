import asyncio, asyncpg, os
async def f():
    c = await asyncpg.connect(os.environ["DATABASE_URL"])
    await c.execute("DELETE FROM users WHERE email = $1", "demo@tracelite.local")
    await c.close()
    print("cleaned demo user + cascaded data")
asyncio.run(f())
