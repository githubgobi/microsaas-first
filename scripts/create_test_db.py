"""
Creates the saas_test database if it does not already exist.
Run this once before pytest — the test suite assumes the database exists.

Uses asyncpg directly (already a project dependency) so there is no
dependency on SQLAlchemy or the application code.
"""
import asyncio
import os
import sys


async def main() -> None:
    try:
        import asyncpg
    except ImportError:
        print("asyncpg not installed — skipping test database creation")
        return

    url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/saas_test",
    )
    # Strip the SQLAlchemy dialect prefix so asyncpg can parse the URL
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    db_name = url.rsplit("/", 1)[-1]
    admin_url = url.rsplit("/", 1)[0] + "/postgres"

    try:
        conn = await asyncpg.connect(admin_url)
    except Exception as e:
        print(f"ERROR: Could not connect to PostgreSQL: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )
        if exists:
            print(f"Database '{db_name}' already exists.")
        else:
            # CREATE DATABASE cannot run inside a transaction.
            # asyncpg uses autocommit by default outside explicit transactions.
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            print(f"Database '{db_name}' created.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
