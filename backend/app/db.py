from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def setup_db(url: str) -> async_sessionmaker[AsyncSession]:
    global _engine, _sessionmaker
    _engine = create_async_engine(url)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _sessionmaker


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    assert _sessionmaker is not None, "setup_db() not called"
    return _sessionmaker


async def init_db() -> None:
    from app import models  # noqa: F401

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
