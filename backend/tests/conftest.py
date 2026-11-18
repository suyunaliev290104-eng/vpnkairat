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


@pytest.fixture
def server_factory(session):
    from app.models import Server

    async def make(**kw) -> Server:
        defaults = dict(
            name="Нидерланды", country="NL", flag="🇳🇱", panel_url="https://nl.example:2053/path",
            username="admin", password="pw", inbound_id=1, host="nl.example", port=443,
            reality_pbk="PBK", reality_sni="www.microsoft.com", reality_sid="ab12", enabled=True,
        )
        defaults.update(kw)
        srv = Server(**defaults)
        session.add(srv)
        await session.commit()
        return srv
    return make
