from functools import wraps
from telegram import Update
from telegram.ext import CallbackContext
from bot.database.connection import AsyncSessionLocal
from bot.repositories.user_repo import UserRepository

def blacklist_check(func):
    """Decorator to block banned or blacklisted users from interacting."""
    @wraps(func)
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = None
        if update.effective_user:
            user_id = update.effective_user.id
            
        if not user_id:
            return await func(update, context, *args, **kwargs)

        async with AsyncSessionLocal() as session:
            user_repo = UserRepository(session)
            # Check bans and blacklist
            is_banned = await user_repo.is_banned(user_id)
            is_black = await user_repo.is_blacklisted(user_id)
            
            if is_banned or is_black:
                if update.callback_query:
                    await update.callback_query.answer("🚫 You are banned or blacklisted from this bot.", show_alert=True)
                elif update.message:
                    await update.message.reply_text("🚫 You are banned or blacklisted from this bot.")
                return

        return await func(update, context, *args, **kwargs)
    return wrapper
