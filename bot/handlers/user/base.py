import logging
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler, CallbackQueryHandler
from bot.database.connection import AsyncSessionLocal
from bot.services.user_service import UserService
from bot.keyboards.user_kb import UserKeyboards
from bot.middlewares.force_join import get_missing_force_joins
from bot.middlewares.blacklist import blacklist_check
from bot.middlewares.rate_limit import rate_limit
from bot.utils.visual import Visual

logger = logging.getLogger(__name__)

@blacklist_check
async def start_command(update: Update, context: CallbackContext):
    """Processes the /start command (including referrals start parameter)."""
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    
    # Check start arguments (for referral tracking)
    args = context.args
    referrer_id = None
    if args and args[0].isdigit():
        referrer_id = int(args[0])

    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        # Register user (checks if new user)
        user, is_new = await user_service.get_or_create_user(
            user_id=user_id,
            username=username,
            first_name=first_name,
            referrer_id=referrer_id
        )
        
        # Check Force Join requirements
        missing = await get_missing_force_joins(user_id, context.bot, session)
        if missing:
            text = (
                f"{Visual.header('Force Join Verification')}\n"
                f"⚠️ You must join our partner channels to unlock the bot features.\n\n"
                f"Please join all channels below and click <b>Verify</b>."
            )
            await update.message.reply_text(
                text=text,
                parse_mode="HTML",
                reply_markup=UserKeyboards.force_join(missing)
            )
            return

        # If they successfully started without any force-joins or already registered
        await show_main_menu(update, context, session, user_id, first_name)

async def show_main_menu(update: Update, context: CallbackContext, session, user_id: int, first_name: str, edit: bool = False):
    """Auxiliary function to render the Main Menu dashboard."""
    # Count unread notifications
    from bot.repositories.admin_repo import AdminRepository
    admin_repo = AdminRepository(session)
    notifs = await admin_repo.get_unread_notifications(user_id)
    unread_count = len(notifs)

    # Get user wallet credits
    from bot.repositories.user_repo import UserRepository
    user_repo = UserRepository(session)
    user = await user_repo.get_user(user_id)
    credits_val = user.credits if user else 0.0

    text = (
        f"{Visual.BORDER}\n"
        f"💎 <b>Money Agent Marketplace</b>\n\n"
        f"👤 User: <b>{first_name}</b>\n"
        f"💰 Balance: <b>{credits_val} Credits</b>\n"
        f"{Visual.BORDER}\n"
        f"Welcome to the premium digital agent marketplace! Explore, purchase, or upload your custom automation agents."
    )

    from bot.config import settings
    is_admin = user_id in settings.ADMIN_IDS
    reply_markup = UserKeyboards.main_menu(unread_notifs=unread_count, is_admin=is_admin)

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    else:
        # If it's a message trigger or callback query not editable
        if update.message:
            await update.message.reply_text(
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        elif update.callback_query:
            await update.callback_query.message.reply_text(
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )

@rate_limit
@blacklist_check
async def verify_join_callback(update: Update, context: CallbackContext):
    """Processes force join verification callbacks."""
    query = update.callback_query
    user_id = query.from_user.id
    
    await query.answer("⏳ Checking channel subscriptions...")

    async with AsyncSessionLocal() as session:
        missing = await get_missing_force_joins(user_id, context.bot, session)
        
        if missing:
            text = (
                f"{Visual.header('Force Join Verification')}\n"
                f"❌ Verification failed. You still haven't joined some channels.\n\n"
                f"Please join remaining channels and click <b>Verify</b>."
            )
            # Edit text with remaining list
            await query.edit_message_text(
                text=text,
                parse_mode="HTML",
                reply_markup=UserKeyboards.force_join(missing)
            )
            return

        # If they successfully verified, distribute referral & welcome reward if applicable
        user_service = UserService(session)
        rewarded, ref_earned, ref_id = await user_service.process_referral_rewards(user_id)
        
        if rewarded:
            # Show premium animation welcome text
            welcome_text = (
                f"🎉 <b>Welcome Bonus Awarded!</b>\n"
                f"{Visual.BORDER}\n"
                f"Congratulations! You received <b>+1 Credit</b> welcome reward.\n"
                f"Your referrer (ID: {ref_id}) received <b>+{ref_earned} Credits</b>.\n"
                f"{Visual.BORDER}"
            )
            await query.edit_message_text(
                text=welcome_text,
                parse_mode="HTML",
                reply_markup=UserKeyboards.back_to_main()
            )
        else:
            # Render standard menu dashboard
            await show_main_menu(update, context, session, user_id, query.from_user.first_name, edit=True)

@rate_limit
@blacklist_check
async def menu_navigation_callback(update: Update, context: CallbackContext):
    """Direct routing callback query navigations."""
    query = update.callback_query
    action = query.data.split(":")[1]
    user_id = query.from_user.id

    async with AsyncSessionLocal() as session:
        if action == "main":
            await show_main_menu(update, context, session, user_id, query.from_user.first_name, edit=True)
            await query.answer()
            
        elif action == "about":
            text = (
                f"{Visual.header('About the Bot')}\n"
                f"🤖 <b>Money Agent Marketplace</b> is an enterprise-grade digital exchange built for Telegram.\n\n"
                f"Earn credits through check-ins, refer friends, and trade bots, files, and automation codes securely.\n\n"
                f"💡 Developer contact: @Himanshu\n"
                f"✨ Version: v1.0.0 (Production)"
            )
            await query.edit_message_text(
                text=text,
                parse_mode="HTML",
                reply_markup=UserKeyboards.back_to_main()
            )
            await query.answer()
            
        elif action == "settings":
            text = (
                f"{Visual.header('User Settings')}\n"
                f"⚙️ Manage your notification settings here.\n\n"
                f"🔔 Push Notifications: <b>Enabled</b>\n"
                f"📩 Daily Reminders: <b>Enabled</b>\n\n"
                f"💡 Contact support if you need to wipe your profile data."
            )
            await query.edit_message_text(
                text=text,
                parse_mode="HTML",
                reply_markup=UserKeyboards.back_to_main()
            )
            await query.answer()
