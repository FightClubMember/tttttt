import datetime
import random
import logging
from functools import wraps
from telegram import Update
from telegram.ext import CallbackContext
from bot.database.connection import AsyncSessionLocal
from bot.repositories.user_repo import UserRepository
from bot.repositories.admin_repo import AdminRepository
from bot.models.user import DailyReward

logger = logging.getLogger(__name__)

async def handle_auto_checkin(user_id: int, update: Update, context: CallbackContext):
    """Checks and claims daily check-in automatically on any interaction."""
    async with AsyncSessionLocal() as session:
        try:
            user_repo = UserRepository(session)
            user = await user_repo.get_user(user_id)
            if not user or user.is_banned or user.is_blacklisted:
                return

            daily = await user_repo.get_daily_reward(user_id)
            now = datetime.datetime.utcnow()

            can_claim = False
            if not daily:
                can_claim = True
            else:
                time_diff = (now - daily.last_check_in).total_seconds()
                if time_diff >= 86400:
                    can_claim = True

            if can_claim:
                # Grant a random float reward between 0.6 and 1.0 Credits
                earned = round(random.uniform(0.6, 1.0), 2)

                if daily:
                    daily.last_check_in = now
                    daily.streak += 1
                else:
                    daily = DailyReward(user_id=user_id, last_check_in=now, streak=1)
                    await user_repo.add(daily)

                user.credits += earned
                user.lifetime_earned += earned

                # Log notification
                admin_repo = AdminRepository(session)
                await admin_repo.add_notification(
                    user_id,
                    f"🎁 Auto Daily Check-in! Claimed +{earned} Credits."
                )
                await session.commit()

                # Trigger alert/reply
                alert_text = f"🎁 Daily check-in claimed automatically! (+{earned} Credits)"
                if update.callback_query:
                    try:
                        await update.callback_query.answer(alert_text, show_alert=True)
                    except Exception:
                        pass
                elif update.message:
                    try:
                        await update.message.reply_text(f"🎉 <b>{alert_text}</b>", parse_mode="HTML")
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Error in auto daily check-in check: {e}")

def blacklist_check(func):
    """Decorator to block banned or blacklisted users from interacting."""
    @wraps(func)
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = None
        if update.effective_user:
            user_id = update.effective_user.id
            
        if not user_id:
            return await func(update, context, *args, **kwargs)

        # Run auto daily check-in check before verifying blacklists
        await handle_auto_checkin(user_id, update, context)

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
