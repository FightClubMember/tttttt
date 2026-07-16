from functools import wraps
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext.filters import UpdateFilter
from bot.config import settings

class AdminFilter(UpdateFilter):
    """Custom python-telegram-bot filter to match only admin users."""
    def filter(self, update: Update) -> bool:
        user_id = update.effective_user.id if update.effective_user else None
        return user_id in settings.ADMIN_IDS if user_id else False

admin_filter = AdminFilter()

def admin_only(func):
    """Decorator to enforce admin privileges on specific handlers."""
    @wraps(func)
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id if update.effective_user else None
        if not user_id or user_id not in settings.ADMIN_IDS:
            if update.callback_query:
                await update.callback_query.answer("⚠️ Access Denied: Admin privileges required.", show_alert=True)
            elif update.message:
                await update.message.reply_text("⚠️ Access Denied: Admin privileges required.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
