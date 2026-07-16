import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler, MessageHandler, ConversationHandler, filters
from bot.database.connection import AsyncSessionLocal
from bot.services.admin_service import AdminService
from bot.repositories.user_repo import UserRepository
from bot.keyboards.admin_kb import AdminKeyboards
from bot.filters.admin_filter import admin_only
from bot.middlewares.blacklist import blacklist_check
from bot.middlewares.rate_limit import rate_limit
from bot.states.fsm import ADMIN_USER_SEARCH, ADMIN_ADD_CREDITS, ADMIN_REMOVE_CREDITS, ADMIN_WARN_USER
from bot.utils.visual import Visual
from bot.utils.otp import OTPProvider
from bot.cache.redis_cache import cache
from bot.handlers.admin.dashboard import admin_dashboard_callback

logger = logging.getLogger(__name__)

# Helper to render user profile card
async def render_user_profile(user_id: int, admin_id: int, bot, bot_msg_id: int, session):
    user_repo = UserRepository(session)
    user = await user_repo.get_user(user_id)
    if not user:
        await bot.edit_message_text(
            chat_id=admin_id,
            message_id=bot_msg_id,
            text="❌ User profile not found.",
            reply_markup=AdminKeyboards.users_menu()
        )
        return

    is_banned = await user_repo.is_banned(user_id)
    is_black = await user_repo.is_blacklisted(user_id)

    text = (
        f"{Visual.header('User Profile')}\n"
        f"👤 User ID: <code>{user.id}</code>\n"
        f"🏷 Username: @{user.username or 'N/A'}\n"
        f"✍️ Name: {user.first_name or 'N/A'}\n"
        f"📅 Joined: {user.joined_at.strftime('%Y-%m-%d')}\n"
        f"🛡 Role: <b>{user.role.upper()}</b>\n\n"
        f"💰 Credits: <b>{user.credits} Credits</b>\n"
        f"📈 Lifetime Earned: <b>{user.lifetime_earned} Credits</b>\n"
        f"📉 Lifetime Spent: <b>{user.lifetime_spent} Credits</b>\n\n"
        f"⚠️ Warnings: <b>{user.warnings_count} / 3</b>\n"
        f"🚫 Status: {'BANNED' if is_banned else 'BLACKLISTED' if is_black else 'ACTIVE'}\n"
        f"{Visual.footer()}"
    )

    await bot.edit_message_text(
        chat_id=admin_id,
        message_id=bot_msg_id,
        text=text,
        parse_mode="HTML",
        reply_markup=AdminKeyboards.user_action_sheet(user_id, is_banned, is_black)
    )

@rate_limit
@blacklist_check
@admin_only
async def admin_users_menu_callback(update: Update, context: CallbackContext):
    """Renders users initial options."""
    query = update.callback_query
    await query.edit_message_text(
        text=f"{Visual.header('User Management')}\nChoose an option to manage marketplace accounts:",
        parse_mode="HTML",
        reply_markup=AdminKeyboards.users_menu()
    )
    await query.answer()

# SEARCH USER FSM FLOW
@rate_limit
@blacklist_check
@admin_only
async def search_user_start_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    text = (
        f"{Visual.header('Search User')}\n"
        f"🔍 Please type the user's Telegram ID or Username:"
    )
    msg = await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=AdminKeyboards.back_to_dash()
    )
    context.user_data["menu_msg_id"] = msg.message_id
    return ADMIN_USER_SEARCH

async def search_user_input_handler(update: Update, context: CallbackContext) -> int:
    message = update.message
    admin_id = message.from_user.id
    query_text = message.text.strip()

    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    if not bot_msg_id:
        return ConversationHandler.END

    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        users = await user_repo.search_users(query_text)
        
        if not users:
            await context.bot.edit_message_text(
                chat_id=admin_id,
                message_id=bot_msg_id,
                text="❌ No users match your query.",
                reply_markup=AdminKeyboards.users_menu()
            )
            return ConversationHandler.END

        # Render first found user profile
        context.user_data["manage_user_id"] = users[0].id
        await render_user_profile(users[0].id, admin_id, context.bot, bot_msg_id, session)

    return ConversationHandler.END

# ADJUST CREDITS FSM FLOWS
@rate_limit
@blacklist_check
@admin_only
async def add_credits_start_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    user_id = int(query.data.split(":")[3])
    context.user_data["manage_user_id"] = user_id

    text = f"💰 Enter the amount of credits to <b>Add</b> to user <code>{user_id}</code>:"
    msg = await query.edit_message_text(text=text, parse_mode="HTML")
    context.user_data["menu_msg_id"] = msg.message_id
    return ADMIN_ADD_CREDITS

async def add_credits_input_handler(update: Update, context: CallbackContext) -> int:
    message = update.message
    admin_id = message.from_user.id
    amount_text = message.text.strip()

    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    user_id = context.user_data.get("manage_user_id")

    if not bot_msg_id or not user_id:
        return ConversationHandler.END

    try:
        amount = float(amount_text)
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await context.bot.edit_message_text(
            chat_id=admin_id, message_id=bot_msg_id, text="⚠️ Invalid amount. Try again:"
        )
        return ADMIN_ADD_CREDITS

    # Secure OTP before adding credits
    await setup_otp_verification(admin_id, bot_msg_id, "add_cr", f"{user_id}:{amount}", context)
    return ConversationHandler.END

# WARNINGS FSM FLOW
@rate_limit
@blacklist_check
@admin_only
async def warn_user_start_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    user_id = int(query.data.split(":")[3])
    context.user_data["manage_user_id"] = user_id

    text = f"⚠️ Type the warning reason for user <code>{user_id}</code>:"
    msg = await query.edit_message_text(text=text, parse_mode="HTML")
    context.user_data["menu_msg_id"] = msg.message_id
    return ADMIN_WARN_USER

async def warn_user_input_handler(update: Update, context: CallbackContext) -> int:
    message = update.message
    admin_id = message.from_user.id
    reason = message.text.strip()

    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    user_id = context.user_data.get("manage_user_id")

    if not bot_msg_id or not user_id:
        return ConversationHandler.END

    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_user(user_id)
        if user:
            user.warnings_count += 1
            # Add notification
            from bot.repositories.admin_repo import AdminRepository
            admin_repo = AdminRepository(session)
            await admin_repo.add_notification(user_id, f"⚠️ Warning Issued! Reason: {reason} ({user.warnings_count}/3).")
            
            # If warning limit reached, auto-ban
            if user.warnings_count >= 3:
                admin_service = AdminService(session)
                await admin_service.ban_user(user_id, "Automatic ban: 3 warnings accumulated.", admin_id)
                await admin_repo.add_notification(user_id, "🔴 You have been banned due to receiving 3 warnings.")

            await session.commit()
            
        await render_user_profile(user_id, admin_id, context.bot, bot_msg_id, session)

    return ConversationHandler.END

# OTP SECURE FLOW SETUP
async def setup_otp_verification(admin_id: int, bot_msg_id: int, action: str, target_payload: str, context: CallbackContext):
    """Sets up an OTP code, saves in cache, and prints the numeric keypad."""
    code = OTPProvider.generate_code()
    
    # Cache OTP config for 120 seconds
    cache_key = f"otp:{admin_id}"
    cache_val = f"{code}:{action}:{target_payload}"
    await cache.set(cache_key, cache_val, ttl=120)

    text = (
        f"🛡 <b>OTP Action Authorization</b>\n"
        f"{Visual.BORDER}\n"
        f"Action: <b>{action.upper()}</b>\n"
        f"To authorize this action, please enter code: <code>{code}</code>\n\n"
        f"Input: <code>{OTPProvider.mask_code('')}</code>"
    )
    
    await context.bot.edit_message_text(
        chat_id=admin_id,
        message_id=bot_msg_id,
        text=text,
        parse_mode="HTML",
        reply_markup=OTPProvider.get_otp_keyboard(action, target_payload, "")
    )

# OTP CALLBACK HANDLER ROUTING
@blacklist_check
@admin_only
async def otp_callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    parts = query.data.split(":")
    action = parts[1]
    target_payload = parts[2]
    current_input = parts[3]
    pressed_val = parts[4]
    admin_id = query.from_user.id

    cache_key = f"otp:{admin_id}"
    cache_val = await cache.get(cache_key)
    
    if not cache_val:
        await query.answer("⌛ OTP session expired or invalid. Please retry.", show_alert=True)
        await admin_dashboard_callback(update, context)
        return

    saved_code, action_type, payload = cache_val.split(":", 2)

    # Cancel trigger
    if pressed_val == "cancel":
        await cache.delete(cache_key)
        await query.answer("🚫 Action cancelled.")
        await admin_dashboard_callback(update, context)
        return

    # Clear trigger
    if pressed_val == "clear":
        new_input = ""
    else:
        new_input = current_input + pressed_val

    # Check length
    if len(new_input) < 4:
        # Edit markup with updated dots
        text = (
            f"🛡 <b>OTP Action Authorization</b>\n"
            f"{Visual.BORDER}\n"
            f"Action: <b>{action_type.upper()}</b>\n"
            f"Enter code: <code>{saved_code}</code>\n\n"
            f"Input: <code>{OTPProvider.mask_code(new_input)}</code>"
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=OTPProvider.get_otp_keyboard(action, target_payload, new_input)
        )
        await query.answer()
        return

    # Verify input length = 4
    if new_input == saved_code:
        await query.answer("✅ OTP Authorized. Executing action...")
        await cache.delete(cache_key)
        
        # Execute authorized action
        async with AsyncSessionLocal() as session:
            admin_service = AdminService(session)
            
            if action_type == "add_cr":
                u_id, amt = payload.split(":")
                await admin_service.adjust_credits(int(u_id), float(amt), admin_id, "add")
                await render_user_profile(int(u_id), admin_id, context.bot, query.message.message_id, session)
                
            elif action_type == "rem_cr":
                u_id, amt = payload.split(":")
                await admin_service.adjust_credits(int(u_id), float(amt), admin_id, "remove")
                await render_user_profile(int(u_id), admin_id, context.bot, query.message.message_id, session)
                
            elif action_type == "reset_wal":
                u_id = int(payload)
                await admin_service.adjust_credits(u_id, 0.0, admin_id, "reset")
                await render_user_profile(u_id, admin_id, context.bot, query.message.message_id, session)
                
            elif action_type == "toggle_ban":
                u_id = int(payload)
                user_repo = UserRepository(session)
                is_banned = await user_repo.is_banned(u_id)
                if is_banned:
                    await admin_service.unban_user(u_id, admin_id)
                else:
                    await admin_service.ban_user(u_id, "Manual ban by administrator.", admin_id)
                await render_user_profile(u_id, admin_id, context.bot, query.message.message_id, session)

            elif action_type == "toggle_black":
                u_id = int(payload)
                user_repo = UserRepository(session)
                is_black = await user_repo.is_blacklisted(u_id)
                if is_black:
                    await admin_service.unblacklist_user(u_id, admin_id)
                else:
                    await admin_service.blacklist_user(u_id, "Fraudulent device check failed.", admin_id)
                await render_user_profile(u_id, admin_id, context.bot, query.message.message_id, session)

            elif action_type == "delete_acc":
                u_id = int(payload)
                user_repo = UserRepository(session)
                user = await user_repo.get_user(u_id)
                if user:
                    await user_repo.delete(user)
                    await session.commit()
                await query.edit_message_text(
                    text="✅ Account deleted permanently.",
                    reply_markup=AdminKeyboards.back_to_dash()
                )
    else:
        await query.answer("❌ Incorrect OTP entered. Access Denied.", show_alert=True)
        await cache.delete(cache_key)
        await admin_dashboard_callback(update, context)

# ROUTE DIRECT TRIGGERS
@blacklist_check
@admin_only
async def usract_routing_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    parts = query.data.split(":")
    action = parts[2]
    user_id = int(parts[3])
    admin_id = query.from_user.id
    msg_id = query.message.message_id

    # Add routing triggers for simple profile checks or OTP pad launching
    if action == "reset_wal":
        await setup_otp_verification(admin_id, msg_id, "reset_wal", str(user_id), context)
    elif action == "toggle_ban":
        await setup_otp_verification(admin_id, msg_id, "toggle_ban", str(user_id), context)
    elif action == "toggle_black":
        await setup_otp_verification(admin_id, msg_id, "toggle_black", str(user_id), context)
    elif action == "delete":
        await setup_otp_verification(admin_id, msg_id, "delete_acc", str(user_id), context)
    elif action == "rem_cr":
        # Launch FSM or OTP for removing credits
        text = f"💰 Enter the amount of credits to <b>Remove</b> from user <code>{user_id}</code>:"
        msg = await query.edit_message_text(text=text, parse_mode="HTML")
        context.user_data["manage_user_id"] = user_id
        # Set state (ConversationHandler handles routing)
        context.user_data["credits_sub_action"] = "remove"
        
        # We can simulate FSM transition
        # But to keep it simple, since we already have a conversation entry point:
        # We will capture this in the ConversationHandler state
        
# Set up conversation handlers
users_search_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(search_start_callback, pattern="^admin:users:search$") if 'search_start_callback' in locals() else CallbackQueryHandler(search_user_start_callback, pattern="^admin:users:search$")],
    states={
        ADMIN_USER_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_user_input_handler)]
    },
    fallbacks=[CallbackQueryHandler(admin_dashboard_callback, pattern="^admin:dashboard$")],
    per_message=False
)

credits_adj_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(add_credits_start_callback, pattern="^admin:usract:add_cr:\\d+$")],
    states={
        ADMIN_ADD_CREDITS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_credits_input_handler)]
    },
    fallbacks=[CallbackQueryHandler(admin_dashboard_callback, pattern="^admin:dashboard$")],
    per_message=False
)

warn_user_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(warn_user_start_callback, pattern="^admin:usract:warn:\\d+$")],
    states={
        ADMIN_WARN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, warn_user_input_handler)]
    },
    fallbacks=[CallbackQueryHandler(admin_dashboard_callback, pattern="^admin:dashboard$")],
    per_message=False
)
