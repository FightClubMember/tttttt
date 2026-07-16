from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot
from telegram.error import TelegramError
from bot.repositories.admin_repo import AdminRepository
from bot.models.settings import ForceJoinChannel

async def get_missing_force_joins(user_id: int, bot: Bot, session: AsyncSession) -> List[ForceJoinChannel]:
    """
    Checks if user has joined all active force join channels.
    Returns a list of channels the user has NOT joined yet.
    """
    admin_repo = AdminRepository(session)
    channels = await admin_repo.get_all_force_join_channels(include_inactive=False)
    
    missing = []
    for chan in channels:
        # If it's an admin user, bypass force join check
        from bot.config import settings
        if user_id in settings.ADMIN_IDS:
            continue
            
        target = chan.channel_username or chan.channel_id
        if not target:
            continue
            
        try:
            member = await bot.get_chat_member(chat_id=target, user_id=user_id)
            if member.status not in ["creator", "administrator", "member"]:
                missing.append(chan)
        except TelegramError as e:
            # If the bot is not admin or channel is unreachable, mark missing as defensive measure
            import logging
            logging.getLogger(__name__).warning(f"Failed to check membership for {target}: {e}")
            missing.append(chan)
            
    return missing
