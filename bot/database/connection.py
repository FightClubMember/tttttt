from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from bot.config import settings

db_url = settings.DATABASE_URL

# Automatically adjust DB scheme for SQLAlchemy Async driver support
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif db_url.startswith("sqlite://") and not db_url.startswith("sqlite+aiosqlite://"):
    db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

# Strip any query parameters (like sslmode, channel_binding) since asyncpg doesn't support them in the connection URL
if "postgresql" in db_url and "?" in db_url:
    db_url = db_url.split("?", 1)[0]

engine_kwargs = {}
if "sqlite" in db_url:
    engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
else:
    # Render Free Postgres connection limit is 5. Restrict pool to avoid FATAL connection limit errors!
    engine_kwargs["pool_size"] = 3
    engine_kwargs["max_overflow"] = 2
    engine_kwargs["pool_recycle"] = 1800
    engine_kwargs["connect_args"] = {"ssl": "require"}

engine = create_async_engine(db_url, echo=False, **engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    """Initializes tables in the database if they don't exist yet (for dev/sqlite)."""
    from bot.models.base import Base
    async with engine.begin() as conn:
        if "sqlite" in db_url:
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            await conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")
        await conn.run_sync(Base.metadata.create_all)
