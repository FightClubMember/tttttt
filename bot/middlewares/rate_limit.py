import time
from functools import wraps
from telegram import Update
from telegram.ext import CallbackContext
from bot.config import settings
from bot.cache.redis_cache import cache

# In-memory rate limiting dictionary (fallback)
user_last_click = {}

def rate_limit(func):
    """Decorator to prevent spamming buttons (cooldown: settings.RATE_LIMIT_COOLDOWN)."""
    @wraps(func)
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = None
        if update.effective_user:
            user_id = update.effective_user.id
            
        if not user_id:
            return await func(update, context, *args, **kwargs)

        now = time.time()
        cooldown = settings.RATE_LIMIT_COOLDOWN

        # Try to use Redis cache for distributed rate limiting if available
        if cache.use_redis:
            cache_key = f"rate_limit:{user_id}"
            last_time_str = await cache.get(cache_key)
            if last_time_str:
                last_time = float(last_time_str)
                if now - last_time < cooldown:
                    if update.callback_query:
                        await update.callback_query.answer("⚠️ Please do not spam buttons!", show_alert=True)
                    return
            await cache.set(cache_key, str(now), ttl=2)
        else:
            # Fallback to local memory dict
            last_time = user_last_click.get(user_id, 0.0)
            if now - last_time < cooldown:
                if update.callback_query:
                    await update.callback_query.answer("⚠️ Please do not spam buttons!", show_alert=True)
                return
            user_last_click[user_id] = now

        return await func(update, context, *args, **kwargs)
    return wrapper
