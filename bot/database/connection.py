from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from bot.config import settings

db_url = settings.DATABASE_URL

# Automatically adjust DB scheme for SQLAlchemy Async driver support
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif db_url.startswith("sqlite://") and not db_url.startswith("sqlite+aiosqlite://"):
    db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

# Strip 'sslmode' query parameter since asyncpg doesn't support it (passes it to connect() causing NameError/TypeError)
if "postgresql" in db_url and "?" in db_url:
    base_url, query = db_url.split("?", 1)
    params = [p for p in query.split("&") if not p.startswith("sslmode=")]
    db_url = f"{base_url}?{'&'.join(params)}" if params else base_url

engine_kwargs = {}
if "sqlite" in db_url:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_size"] = 20
    engine_kwargs["max_overflow"] = 10
    engine_kwargs["pool_recycle"] = 1800
    engine_kwargs["connect_args"] = {"ssl": "require"}

engine = create_async_engine(db_url, echo=False, **engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    """Initializes tables in the database if they don't exist yet (for dev/sqlite)."""
    from bot.models.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
