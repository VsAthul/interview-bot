# app/database.py
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,          # set True to see SQL queries while debugging
    connect_args={"check_same_thread": False}  # required for SQLite
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)

class Base(DeclarativeBase):
    pass

# FastAPI dependency — injects a DB session into every route
async def get_db()->AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Called once at startup to create all tables
async def init_db()->None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)