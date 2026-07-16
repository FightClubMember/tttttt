from typing import List, Optional, Tuple
from sqlalchemy import select, func, or_
from bot.repositories.base import BaseRepository
from bot.models.user import User, Referral, DailyReward, Blacklist, Ban

class UserRepository(BaseRepository):
    async def get_user(self, user_id: int) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        res = await self.execute(stmt)
        return res.scalar_one_or_none()

    async def create_user(self, user_id: int, username: str, first_name: str, referrer_id: Optional[int] = None) -> User:
        user = User(
            id=user_id,
            username=username,
            first_name=first_name,
            referrer_id=referrer_id
        )
        await self.add(user)
        return user

    async def get_all_users(self) -> List[User]:
        stmt = select(User)
        res = await self.execute(stmt)
        return list(res.scalars().all())

    async def search_users(self, query: str) -> List[User]:
        """Search users by ID, username, or first name."""
        stmt = select(User)
        if query.isdigit():
            stmt = stmt.where(or_(User.id == int(query), User.username.ilike(f"%{query}%")))
        else:
            stmt = stmt.where(or_(
                User.username.ilike(f"%{query}%"),
                User.first_name.ilike(f"%{query}%")
            ))
        res = await self.execute(stmt)
        return list(res.scalars().all())

    async def get_daily_reward(self, user_id: int) -> Optional[DailyReward]:
        stmt = select(DailyReward).where(DailyReward.user_id == user_id)
        res = await self.execute(stmt)
        return res.scalar_one_or_none()

    async def get_referral(self, referrer_id: int, referee_id: int) -> Optional[Referral]:
        stmt = select(Referral).where(Referral.referrer_id == referrer_id, Referral.referee_id == referee_id)
        res = await self.execute(stmt)
        return res.scalar_one_or_none()

    async def get_referrals_by_referee(self, referee_id: int) -> List[Referral]:
        stmt = select(Referral).where(Referral.referee_id == referee_id)
        res = await self.execute(stmt)
        return list(res.scalars().all())

    async def get_referral_count(self, user_id: int) -> int:
        stmt = select(func.count(Referral.id)).where(Referral.referrer_id == user_id, Referral.status == "verified")
        res = await self.execute(stmt)
        return res.scalar() or 0

    async def get_referral_leaderboard(self, limit: int = 10) -> List[Tuple[User, int]]:
        """Returns top users by referral count."""
        stmt = (
            select(User, func.count(Referral.id).label("ref_count"))
            .join(Referral, Referral.referrer_id == User.id)
            .where(Referral.status == "verified")
            .group_by(User.id)
            .order_by(func.count(Referral.id).desc())
            .limit(limit)
        )
        res = await self.execute(stmt)
        return [(row[0], row[1]) for row in res.all()]

    async def is_blacklisted(self, user_id: int) -> bool:
        stmt = select(Blacklist).where(Blacklist.user_id == user_id)
        res = await self.execute(stmt)
        return res.scalar_one_or_none() is not None

    async def is_banned(self, user_id: int) -> bool:
        stmt = select(Ban).where(Ban.user_id == user_id)
        res = await self.execute(stmt)
        return res.scalar_one_or_none() is not None

    async def get_blacklist(self, user_id: int) -> Optional[Blacklist]:
        stmt = select(Blacklist).where(Blacklist.user_id == user_id)
        res = await self.execute(stmt)
        return res.scalar_one_or_none()

    async def get_ban(self, user_id: int) -> Optional[Ban]:
        stmt = select(Ban).where(Ban.user_id == user_id)
        res = await self.execute(stmt)
        return res.scalar_one_or_none()
