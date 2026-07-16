import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler, MessageHandler, ConversationHandler, filters
from bot.database.connection import AsyncSessionLocal
from bot.services.broadcast_service import BroadcastService
from bot.models.logs import Broadcast
from bot.keyboards.admin_kb import AdminKeyboards
from bot.filters.admin_filter import admin_only
from bot.middlewares.blacklist import blacklist_check
from bot.middlewares.rate_limit import rate_limit
from bot.states.fsm import ADMIN_BROADCAST_GET_MSG
from bot.utils.visual import Visual

logger = logging.getLogger(__name__)

@rate_limit
@blacklist_check
@admin_only
async def admin_broadcast_menu_callback(update: Update, context: CallbackContext):
    """Renders target selection menu for broadcasting."""
    query = update.callback_query
    await query.edit_message_text(
        text=f"{Visual.header('Broadcast System')}\nSelect target group to start message broadcasting:",
        parse_mode="HTML",
        reply_markup=AdminKeyboards.broadcast_menu()
    )
    await query.answer()

# BROADCAST FSM SETUP
@rate_limit
@blacklist_check
@admin_only
async def broadcast_start_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    target = query.data.split(":")[3]
    context.user_data["broadcast_target"] = target

    text = (
        f"{Visual.header('Broadcast System')}\n"
        f"🎯 Target Group: <b>{target.upper()}</b>\n\n"
        f"✍️ Please send or forward the message you want to broadcast (supports Text, Photos, Videos, Audios, Polls, or buttons):"
    )
    msg = await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=AdminKeyboards.back_to_dash()
    )
    context.user_data["menu_msg_id"] = msg.message_id
    return ADMIN_BROADCAST_GET_MSG

async def broadcast_message_handler(update: Update, context: CallbackContext) -> int:
    message = update.message
    admin_id = message.from_user.id
    target = context.user_data.get("broadcast_target", "all")
    bot_msg_id = context.user_data.get("menu_msg_id")

    if not bot_msg_id:
        return ConversationHandler.END

    # Save target message IDs
    context.user_data["broadcast_chat_id"] = message.chat_id
    context.user_data["broadcast_msg_id"] = message.message_id

    # Show preview to Admin
    await message.reply_text("👇 <b>BROADCAST PREVIEW MESSAGE:</b>", parse_mode="HTML")
    await context.bot.copy_message(
        chat_id=admin_id,
        from_chat_id=message.chat_id,
        message_id=message.message_id
    )

    # Edit control menu to confirm launch
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Start Broadcast", callback_data="admin:broadcast:confirm_send")],
        [InlineKeyboardButton("🚫 Cancel", callback_data="admin:dashboard")]
    ])

    await context.bot.send_message(
        chat_id=admin_id,
        text=f"Check preview above. Click below to begin dispatch to: <b>{target.upper()}</b>.",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    return ConversationHandler.END

@rate_limit
@blacklist_check
@admin_only
async def broadcast_confirm_send_callback(update: Update, context: CallbackContext):
    """Triggers the broadcast loop and launches progress-tracking background job."""
    query = update.callback_query
    admin_id = query.from_user.id
    target = context.user_data.get("broadcast_target", "all")
    from_chat_id = context.user_data.get("broadcast_chat_id")
    message_id = context.user_data.get("broadcast_msg_id")

    if not from_chat_id or not message_id:
        await query.answer("Error: preview missing. Resetting dashboard.", show_alert=True)
        await admin_broadcast_menu_callback(update, context)
        return

    async with AsyncSessionLocal() as session:
        # Create broadcast record
        b_rec = Broadcast(admin_id=admin_id, status="pending")
        session.add(b_rec)
        await session.commit()
        await session.refresh(b_rec)
        broadcast_id = b_rec.id

        # Start async broadcaster task
        broadcaster = BroadcastService(session, context.bot)
        await broadcaster.start_broadcast(
            broadcast_id=broadcast_id,
            from_chat_id=from_chat_id,
            message_id=message_id,
            target_group=target
        )

        # Notify admin progress status
        msg = await query.edit_message_text(
            text=f"🚀 <b>Broadcast Launched!</b>\nStarting dispatch sequence for ID #{broadcast_id}...",
            reply_markup=AdminKeyboards.broadcast_running(broadcast_id)
        )

        # Register a repeating job queue tracker to update admin screen every 3 seconds
        context.job_queue.run_repeating(
            callback=update_broadcast_progress_job,
            interval=3,
            first=1,
            name=f"track_broadcast_{broadcast_id}",
            data={
                "admin_id": admin_id,
                "msg_id": msg.message_id,
                "broadcast_id": broadcast_id
            }
        )
        await query.answer()

async def update_broadcast_progress_job(context: CallbackContext):
    """Periodic job updating progress bar inside admin message card."""
    job = context.job
    data = job.data
    admin_id = data["admin_id"]
    msg_id = data["msg_id"]
    broadcast_id = data["broadcast_id"]

    async with AsyncSessionLocal() as session:
        # Query stats
        from sqlalchemy import select
        res = await session.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
        b_rec = res.scalar_one_or_none()
        
        if not b_rec:
            job.schedule_removal()
            return

        total = b_rec.total_users
        sent = b_rec.delivered + b_rec.failed + b_rec.blocked
        progress_str = Visual.progress_bar(sent, total)

        text = (
            f"📣 <b>Broadcast Dispatch Progress</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏷 Broadcast ID: #{broadcast_id}\n"
            f"⚡ Status: <b>{b_rec.status.upper()}</b>\n\n"
            f"✅ Delivered: <b>{b_rec.delivered}</b>\n"
            f"❌ Failures: <b>{b_rec.failed}</b>\n"
            f"🚫 Blocks: <b>{b_rec.blocked}</b>\n\n"
            f"📊 Progress: {progress_str}"
        )

        if b_rec.status in ["completed", "cancelled", "failed"]:
            # Finish job
            job.schedule_removal()
            keyboard = AdminKeyboards.back_to_dash()
            text += "\n\n🏁 <b>Broadcast operation completed.</b>"
        else:
            keyboard = AdminKeyboards.broadcast_running(broadcast_id)

        try:
            await context.bot.edit_message_text(
                chat_id=admin_id,
                message_id=msg_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except Exception:
            pass

@rate_limit
@blacklist_check
@admin_only
async def admin_broadcast_cancel_callback(update: Update, context: CallbackContext):
    """Cancels running broadcast."""
    query = update.callback_query
    broadcast_id = int(query.data.split(":")[3])

    async with AsyncSessionLocal() as session:
        broadcaster = BroadcastService(session, context.bot)
        await broadcaster.cancel_broadcast(broadcast_id)
        await query.answer("🚫 Broadcast cancellation requested.")

broadcast_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(broadcast_start_callback, pattern="^admin:broadcast:start:\\w+$")],
    states={
        ADMIN_BROADCAST_GET_MSG: [MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_message_handler)]
    },
    fallbacks=[CallbackQueryHandler(admin_broadcast_menu_callback, pattern="^admin:dashboard$")],
    per_message=False
)
