import logging
from telegram import Update
from telegram.ext import CallbackContext, CallbackQueryHandler, MessageHandler, ConversationHandler, filters
from bot.database.connection import AsyncSessionLocal
from bot.repositories.admin_repo import AdminRepository
from bot.models.settings import ForceJoinChannel
from bot.keyboards.admin_kb import AdminKeyboards
from bot.filters.admin_filter import admin_only
from bot.middlewares.blacklist import blacklist_check
from bot.middlewares.rate_limit import rate_limit
from bot.states.fsm import ADMIN_ADD_CHANNEL
from bot.utils.visual import Visual

logger = logging.getLogger(__name__)

@rate_limit
@blacklist_check
@admin_only
async def admin_force_join_menu_callback(update: Update, context: CallbackContext):
    """Lists force join channels."""
    query = update.callback_query
    
    async with AsyncSessionLocal() as session:
        admin_repo = AdminRepository(session)
        channels = await admin_repo.get_all_force_join_channels(include_inactive=True)

        text = f"{Visual.header('Force Join Channels')}\nSelect a channel to edit or delete:"
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=AdminKeyboards.force_join_menu(channels)
        )
        await query.answer()

@rate_limit
@blacklist_check
@admin_only
async def admin_channel_edit_callback(update: Update, context: CallbackContext):
    """Shows options for a specific channel."""
    query = update.callback_query
    chan_id = int(query.data.split(":")[3])

    async with AsyncSessionLocal() as session:
        admin_repo = AdminRepository(session)
        chan = await admin_repo.get_force_join_channel(chan_id)
        if not chan:
            await query.answer("Channel record not found.", show_alert=True)
            return

        text = (
            f"{Visual.header('Channel Settings')}\n"
            f"👤 Username: <b>{chan.channel_username or 'Private Invite Link'}</b>\n"
            f"🔗 Invite Link: <code>{chan.invite_link or 'None'}</code>\n"
            f"🟢 Active: <b>{chan.is_active}</b>\n"
            f"📦 Order: <b>{chan.order}</b>"
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=AdminKeyboards.force_join_edit(chan_id, chan.is_active)
        )
        await query.answer()

@rate_limit
@blacklist_check
@admin_only
async def admin_toggle_channel_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    chan_id = int(query.data.split(":")[3])

    async with AsyncSessionLocal() as session:
        admin_repo = AdminRepository(session)
        chan = await admin_repo.get_force_join_channel(chan_id)
        if chan:
            chan.is_active = not chan.is_active
            await session.commit()
            await query.answer("🟢 Channel status updated!")
            
        await admin_force_join_menu_callback(update, context)

@rate_limit
@blacklist_check
@admin_only
async def admin_delete_channel_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    chan_id = int(query.data.split(":")[3])

    async with AsyncSessionLocal() as session:
        admin_repo = AdminRepository(session)
        chan = await admin_repo.get_force_join_channel(chan_id)
        if chan:
            await admin_repo.delete(chan)
            await session.commit()
            await query.answer("🗑 Channel deleted.")
            
        await admin_force_join_menu_callback(update, context)

# ADD CHANNEL FSM FLOW
@rate_limit
@blacklist_check
@admin_only
async def add_channel_start_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    text = (
        f"{Visual.header('Add Force Join Channel')}\n"
        f"📢 Please type the channel username (e.g. @mychannel) or send the private invite link:"
    )
    msg = await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=AdminKeyboards.back_to_dash()
    )
    context.user_data["menu_msg_id"] = msg.message_id
    return ADMIN_ADD_CHANNEL

async def add_channel_input_handler(update: Update, context: CallbackContext) -> int:
    message = update.message
    admin_id = message.from_user.id
    input_text = message.text.strip()

    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    if not bot_msg_id:
        return ConversationHandler.END

    async with AsyncSessionLocal() as session:
        admin_repo = AdminRepository(session)
        
        # Parse username or invite link
        username = None
        invite_link = None
        if input_text.startswith("@"):
            username = input_text
        elif "t.me/" in input_text:
            invite_link = input_text
            # Try to extract username if public
            if "/joinchat/" not in input_text and "+" not in input_text:
                parts = input_text.split("/")
                username = f"@{parts[-1]}"
        else:
            username = f"@{input_text}"

        # Resolve channel ID if username provided
        channel_id = None
        if username:
            try:
                chat = await context.bot.get_chat(username)
                channel_id = chat.id
            except Exception as e:
                logger.warning(f"Could not fetch channel ID for {username}: {e}. Saving string username only.")

        # Create record
        chan = ForceJoinChannel(
            channel_id=channel_id,
            channel_username=username,
            invite_link=invite_link,
            is_active=True
        )
        await admin_repo.add(chan)
        await session.commit()

        await context.bot.edit_message_text(
            chat_id=admin_id,
            message_id=bot_msg_id,
            text=f"{Visual.header('Channel Added')}\n✅ Channel successfully linked for verification checks.",
            reply_markup=AdminKeyboards.back_to_dash()
        )

    return ConversationHandler.END

channel_add_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(add_channel_start_callback, pattern="^admin:fj:add$")],
    states={
        ADMIN_ADD_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_input_handler)]
    },
    fallbacks=[CallbackQueryHandler(admin_force_join_menu_callback, pattern="^admin:menu:forcejoin$")],
    per_message=False
)
