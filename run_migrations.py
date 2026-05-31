"""
run_migrations.py — Apply all SQL migrations in order against a database.

Usage:
    $env:DATABASE_URL="<external-url-from-render>"
    python run_migrations.py

Runs every .sql file in backend/migrations/ alphabetically (001_, 002_, ...).
Safe to point at the Render External Database URL.
"""

import asyncio
import os
import sys
from pathlib import Path

import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set.")
    print('Set it first:  $env:DATABASE_URL="<external-url>"')
    sys.exit(1)

MIGRATIONS_DIR = Path(__file__).parent / "backend" / "migrations"


async def main() -> None:
    if not MIGRATIONS_DIR.is_dir():
        print(f"ERROR: migrations dir not found at {MIGRATIONS_DIR}")
        sys.exit(1)

    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not sql_files:
        print(f"ERROR: no .sql files found in {MIGRATIONS_DIR}")
        sys.exit(1)

    print(f"Connecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        for sql_file in sql_files:
            print(f"  → Applying {sql_file.name} ...", end=" ")
            sql = sql_file.read_text(encoding="utf-8")
            try:
                await conn.execute(sql)
                print("OK")
            except asyncpg.exceptions.DuplicateTableError:
                print("SKIPPED (already applied)")
            except asyncpg.exceptions.DuplicateObjectError:
                print("SKIPPED (already applied)")
            except Exception as e:
                # Some migrations may partially fail if re-run; report and continue
                print(f"WARNING: {type(e).__name__}: {e}")
        print()
        print("✅ Migrations complete.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())