import asyncio
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.db import Base
from app.main import app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://shipyard:shipyard@localhost:5432/shipyard_test",
)


@pytest.fixture()
def client():
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    get_settings.cache_clear()

    engine = create_async_engine(TEST_DATABASE_URL)

    async def _prepare() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(text("TRUNCATE TABLE ships"))

    asyncio.run(_prepare())

    with TestClient(app) as test_client:
        yield test_client

    asyncio.run(engine.dispose())
    os.environ.pop("DATABASE_URL", None)
    get_settings.cache_clear()
