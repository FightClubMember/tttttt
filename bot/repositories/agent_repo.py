from typing import List, Optional
from sqlalchemy import select, func, desc, asc, or_
from sqlalchemy.orm import selectinload
from bot.repositories.base import BaseRepository
from bot.models.agent import Category, Agent, Order, OrderItem, Favorite, Wishlist

class AgentRepository(BaseRepository):
    # Category operations
    async def get_category(self, category_id: int) -> Optional[Category]:
        stmt = select(Category).where(Category.id == category_id)
        res = await self.execute(stmt)
        return res.scalar_one_or_none()

    async def get_all_categories(self, include_hidden: bool = False) -> List[Category]:
        stmt = select(Category)
        if not include_hidden:
            stmt = stmt.where(Category.is_hidden == False)
        stmt = stmt.order_by(Category.order.asc(), Category.name.asc())
        res = await self.execute(stmt)
        return list(res.scalars().all())

    # Agent operations
    async def get_agent(self, agent_id: int) -> Optional[Agent]:
        stmt = select(Agent).where(Agent.id == agent_id)
        res = await self.execute(stmt)
        return res.scalar_one_or_none()

    async def get_agents_by_category(self, category_id: int, include_hidden: bool = False) -> List[Agent]:
        stmt = select(Agent).where(Agent.category_id == category_id)
        if not include_hidden:
            stmt = stmt.where(Agent.status == "active")
        res = await self.execute(stmt)
        return list(res.scalars().all())

    async def search_agents(self, query: str, category_id: Optional[int] = None, sort_by: str = "newest") -> List[Agent]:
        """Search agents by name, description with sorting options."""
        stmt = select(Agent).where(Agent.status == "active")
        
        if category_id is not None:
            stmt = stmt.where(Agent.category_id == category_id)
            
        if query:
            stmt = stmt.where(or_(
                Agent.name.ilike(f"%{query}%"),
                Agent.description.ilike(f"%{query}%")
            ))
            
        # Sorting
        if sort_by == "newest":
            stmt = stmt.order_by(desc(Agent.created_at))
        elif sort_by == "trending":
            stmt = stmt.where(Agent.is_trending == True).order_by(desc(Agent.downloads))
        elif sort_by == "popular":
            stmt = stmt.order_by(desc(Agent.downloads))
        elif sort_by == "highest_rated":
            stmt = stmt.order_by(desc(Agent.rating))
        elif sort_by == "price_low":
            stmt = stmt.order_by(asc(Agent.price))
        elif sort_by == "price_high":
            stmt = stmt.order_by(desc(Agent.price))
            
        res = await self.execute(stmt)
        return list(res.scalars().all())

    # Orders & Financial logs
    async def get_order(self, order_id: int) -> Optional[Order]:
        stmt = select(Order).where(Order.id == order_id).options(selectinload(Order.items).selectinload(OrderItem.agent))
        res = await self.execute(stmt)
        return res.scalar_one_or_none()

    async def get_user_orders(self, user_id: int) -> List[Order]:
        stmt = select(Order).where(Order.buyer_id == user_id).options(selectinload(Order.items).selectinload(OrderItem.agent)).order_by(desc(Order.purchased_at))
        res = await self.execute(stmt)
        return list(res.scalars().all())

    async def get_user_sales(self, seller_id: int) -> List[OrderItem]:
        stmt = (
            select(OrderItem)
            .join(Agent)
            .join(Order, OrderItem.order_id == Order.id)
            .where(Agent.seller_id == seller_id)
            .options(selectinload(OrderItem.agent), selectinload(OrderItem.order))
            .order_by(desc(Order.purchased_at))
        )
        res = await self.execute(stmt)
        return list(res.scalars().all())

    # Favorites
    async def get_favorites(self, user_id: int) -> List[Agent]:
        stmt = select(Agent).join(Favorite, Favorite.agent_id == Agent.id).where(Favorite.user_id == user_id)
        res = await self.execute(stmt)
        return list(res.scalars().all())

    async def is_favorite(self, user_id: int, agent_id: int) -> bool:
        stmt = select(Favorite).where(Favorite.user_id == user_id, Favorite.agent_id == agent_id)
        res = await self.execute(stmt)
        return res.scalar_one_or_none() is not None

    async def add_favorite(self, user_id: int, agent_id: int):
        fav = Favorite(user_id=user_id, agent_id=agent_id)
        await self.add(fav)

    async def remove_favorite(self, user_id: int, agent_id: int):
        stmt = select(Favorite).where(Favorite.user_id == user_id, Favorite.agent_id == agent_id)
        res = await self.execute(stmt)
        fav = res.scalar_one_or_none()
        if fav:
            await self.delete(fav)

    # Wishlist
    async def get_wishlist(self, user_id: int) -> List[Agent]:
        stmt = select(Agent).join(Wishlist, Wishlist.agent_id == Agent.id).where(Wishlist.user_id == user_id)
        res = await self.execute(stmt)
        return list(res.scalars().all())

    async def is_in_wishlist(self, user_id: int, agent_id: int) -> bool:
        stmt = select(Wishlist).where(Wishlist.user_id == user_id, Wishlist.agent_id == agent_id)
        res = await self.execute(stmt)
        return res.scalar_one_or_none() is not None

    async def add_to_wishlist(self, user_id: int, agent_id: int):
        wl = Wishlist(user_id=user_id, agent_id=agent_id)
        await self.add(wl)

    async def remove_from_wishlist(self, user_id: int, agent_id: int):
        stmt = select(Wishlist).where(Wishlist.user_id == user_id, Wishlist.agent_id == agent_id)
        res = await self.execute(stmt)
        wl = res.scalar_one_or_none()
        if wl:
            await self.delete(wl)

    # Seller moderation queue
    async def get_pending_moderation_queue(self) -> List[Agent]:
        stmt = select(Agent).where(Agent.status == "pending").order_by(desc(Agent.created_at))
        res = await self.execute(stmt)
        return list(res.scalars().all())

    # Reviews and Ratings calculation
    async def get_agent_reviews(self, agent_id: int) -> List[OrderItem]:
        stmt = select(OrderItem).where(OrderItem.agent_id == agent_id, OrderItem.rating != None).order_by(desc(OrderItem.rated_at))
        res = await self.execute(stmt)
        return list(res.scalars().all())

    async def update_agent_rating(self, agent_id: int):
        """Re-calculates and saves the average rating of an agent."""
        stmt = select(func.avg(OrderItem.rating)).where(OrderItem.agent_id == agent_id, OrderItem.rating != None)
        res = await self.execute(stmt)
        avg_rating = res.scalar()
        
        agent = await self.get_agent(agent_id)
        if agent and avg_rating is not None:
            agent.rating = round(float(avg_rating), 1)
