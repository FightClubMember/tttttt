import logging
from telegram import Update
from telegram.ext import CallbackContext, CallbackQueryHandler
from bot.database.connection import AsyncSessionLocal
from bot.services.user_service import UserService
from bot.keyboards.user_kb import UserKeyboards
from bot.middlewares.blacklist import blacklist_check
from bot.middlewares.rate_limit import rate_limit
from bot.utils.visual import Visual

logger = logging.getLogger(__name__)

@rate_limit
@blacklist_check
async def check_in_callback(update: Update, context: CallbackContext):
    """Executes the daily check-in and updates credits."""
    query = update.callback_query
    user_id = query.from_user.id

    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        success, message, earned = await user_service.check_in(user_id)

        if not success:
            # Cooldown message
            await query.edit_message_text(
                text=f"{Visual.header('Daily Check-in')}\n❌ <b>Failed:</b> {message}\n{Visual.footer()}",
                parse_mode="HTML",
                reply_markup=UserKeyboards.back_to_main()
            )
            await query.answer("🕒 Cooldown active!")
            return

        # Success message
        await query.edit_message_text(
            text=f"{Visual.header('Daily Check-in')}\n{message}\n{Visual.footer()}",
            parse_mode="HTML",
            reply_markup=UserKeyboards.back_to_main()
        )
        await query.answer(f"🎁 Claimed +{earned} credits!")
