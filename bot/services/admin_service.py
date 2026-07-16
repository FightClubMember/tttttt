import json
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from bot.repositories.user_repo import UserRepository
from bot.repositories.admin_repo import AdminRepository
from bot.repositories.agent_repo import AgentRepository
from bot.models.user import Blacklist, Ban, User
from bot.models.agent import Category

class AdminService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.admin_repo = AdminRepository(session)
        self.agent_repo = AgentRepository(session)

    async def ban_user(self, user_id: int, reason: str, banned_by: int) -> bool:
        """Bans a user, blocking all interactions."""
        user = await self.user_repo.get_user(user_id)
        if not user:
            return False
            
        user.is_banned = True
        
        # Check if already has ban entry
        ban = await self.user_repo.get_ban(user_id)
        if not ban:
            ban = Ban(user_id=user_id, reason=reason, banned_by=banned_by)
            await self.user_repo.add(ban)
            
        await self.admin_repo.add_audit_log(banned_by, "BAN_USER", f"Banned user {user_id}. Reason: {reason}")
        await self.session.commit()
        return True

    async def unban_user(self, user_id: int, admin_id: int) -> bool:
        """Unbans a user."""
        user = await self.user_repo.get_user(user_id)
        if not user:
            return False
            
        user.is_banned = False
        
        ban = await self.user_repo.get_ban(user_id)
        if ban:
            await self.user_repo.delete(ban)
            
        await self.admin_repo.add_audit_log(admin_id, "UNBAN_USER", f"Unbanned user {user_id}")
        await self.session.commit()
        return True

    async def blacklist_user(self, user_id: int, reason: str, admin_id: int) -> bool:
        """Blacklists a user (permanent device/account fraud prevention)."""
        user = await self.user_repo.get_user(user_id)
        if not user:
            return False
            
        user.is_blacklisted = True
        
        blacklist = await self.user_repo.get_blacklist(user_id)
        if not blacklist:
            blacklist = Blacklist(user_id=user_id, reason=reason)
            await self.user_repo.add(blacklist)
            
        await self.admin_repo.add_audit_log(admin_id, "BLACKLIST_USER", f"Blacklisted user {user_id}. Reason: {reason}")
        await self.session.commit()
        return True

    async def unblacklist_user(self, user_id: int, admin_id: int) -> bool:
        """Removes a user from blacklist."""
        user = await self.user_repo.get_user(user_id)
        if not user:
            return False
            
        user.is_blacklisted = False
        
        blacklist = await self.user_repo.get_blacklist(user_id)
        if blacklist:
            await self.user_repo.delete(blacklist)
            
        await self.admin_repo.add_audit_log(admin_id, "UNBLACKLIST_USER", f"Unblacklisted user {user_id}")
        await self.session.commit()
        return True

    async def adjust_credits(self, user_id: int, amount: float, admin_id: int, action: str = "add") -> Tuple[bool, str]:
        """Adjusts (adds/removes) user credits."""
        user = await self.user_repo.get_user(user_id)
        if not user:
            return False, "User profile not found."

        if action == "add":
            user.credits += amount
            user.lifetime_earned += amount
            detail_msg = f"Added {amount} Credits to user {user_id}."
            await self.admin_repo.add_notification(user_id, f"💰 Admins credited +{amount} Credits to your wallet.")
        elif action == "remove":
            if user.credits < amount:
                amount = user.credits  # Cap at zero
            user.credits -= amount
            detail_msg = f"Deducted {amount} Credits from user {user_id}."
            await self.admin_repo.add_notification(user_id, f"💸 Admins deducted -{amount} Credits from your wallet.")
        elif action == "reset":
            user.credits = 0.0
            detail_msg = f"Reset credits for user {user_id} to 0."
            await self.admin_repo.add_notification(user_id, "💸 Admins reset your credit balance to zero.")
            
        await self.admin_repo.add_audit_log(admin_id, "ADJUST_CREDITS", detail_msg)
        await self.session.commit()
        return True, "Balance adjusted successfully."

    async def bulk_adjust_credits(self, amount: float, admin_id: int, action: str = "add") -> int:
        """Adjusts credits for all registered users. Returns count modified."""
        users = await self.user_repo.get_all_users()
        count = 0
        for user in users:
            if action == "add":
                user.credits += amount
                user.lifetime_earned += amount
                await self.admin_repo.add_notification(user.id, f"💰 Admins bulk-credited +{amount} Credits to everyone.")
            elif action == "remove":
                if user.credits < amount:
                    user.credits = 0.0
                else:
                    user.credits -= amount
                await self.admin_repo.add_notification(user.id, f"💸 Admins bulk-deducted -{amount} Credits from everyone.")
            count += 1
            
        await self.admin_repo.add_audit_log(admin_id, "BULK_CREDITS", f"Bulk {action}ed {amount} credits to {count} users.")
        await self.session.commit()
        return count

    # Categories CRUD
    async def create_category(self, name: str, icon: str = "🤖", banner_url: Optional[str] = None) -> Category:
        """Creates a new marketplace category."""
        # Find next order position
        categories = await self.agent_repo.get_all_categories(include_hidden=True)
        next_order = len(categories) + 1
        
        cat = Category(name=name, icon=icon, banner_url=banner_url, order=next_order)
        await self.agent_repo.add(cat)
        await self.session.commit()
        return cat

    async def delete_category(self, category_id: int, admin_id: int) -> bool:
        """Deletes a category and cascades to delete all child agents."""
        cat = await self.agent_repo.get_category(category_id)
        if not cat:
            return False
            
        await self.agent_repo.delete(cat)
        await self.admin_repo.add_audit_log(admin_id, "DELETE_CATEGORY", f"Deleted category #{category_id} ('{cat.name}')")
        await self.session.commit()
        return True
