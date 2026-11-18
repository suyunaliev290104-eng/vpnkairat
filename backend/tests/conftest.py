import itertools

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base
from app import models  # noqa: F401
from app.models import User

_ids = itertools.count(1000)


@pytest.fixture
async def sessionmaker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def session(sessionmaker):
    async with sessionmaker() as s:
        yield s


@pytest.fixture
def user_factory(session):
    async def make(**kw) -> User:
        u = User(tg_id=kw.pop("tg_id", next(_ids)), username=kw.pop("username", "u"), **kw)
        session.add(u)
        await session.commit()
        return u
    return make
