"""Интеграционные тесты работают с отдельной базой, не с игровыми профилями."""

import asyncio
import os
from pathlib import Path
import re
import subprocess
import sys

import asyncpg
from sqlalchemy.engine import make_url

from src.persistence.settings import get_database_settings

source_url = make_url(get_database_settings().database_url)
database_name = source_url.database or ""
test_database_name = (
    database_name if database_name.endswith("_test") else f"{database_name}_test"
)
if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", test_database_name):
    raise RuntimeError("Невозможно получить безопасное имя тестовой базы")
os.environ["DATABASE_URL"] = source_url.set(
    database=test_database_name
).render_as_string(hide_password=False)


def pytest_sessionstart(session):
    async def ensure_test_database():
        connection = await asyncpg.connect(
            host=source_url.host,
            port=source_url.port or 5432,
            user=source_url.username,
            password=source_url.password,
            database=database_name,
        )
        try:
            exists = await connection.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", test_database_name
            )
            if not exists:
                await connection.execute(f'CREATE DATABASE "{test_database_name}"')
        finally:
            await connection.close()

    asyncio.run(ensure_test_database())
    repository_root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=repository_root,
        check=True,
    )
