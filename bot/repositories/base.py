from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class BaseRepository:
    """Base repository class providing fundamental CRUD operations."""
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, entity):
        """Adds an entity to the session database session."""
        self.session.add(entity)
        return entity

    async def delete(self, entity):
        """Deletes an entity from the session."""
        await self.session.delete(entity)

    async def commit(self):
        """Commits transaction modifications."""
        await self.session.commit()

    async def refresh(self, entity):
        """Refreshes state attributes of an instance."""
        await self.session.refresh(entity)
        return entity

    async def execute(self, statement):
        """Executes a SQLAlchemy statement."""
        return await self.session.execute(statement)
