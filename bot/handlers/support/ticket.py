import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler, MessageHandler, ConversationHandler, filters
from bot.database.connection import AsyncSessionLocal
from bot.repositories.admin_repo import AdminRepository
from bot.models.ticket import Ticket, TicketMessage
from bot.keyboards.user_kb import UserKeyboards
from bot.middlewares.blacklist import blacklist_check
from bot.middlewares.rate_limit import rate_limit
from bot.utils.visual import Visual

logger = logging.getLogger(__name__)

# FSM states
TICKET_SUBJ_STATE = 300
TICKET_MSG_STATE = 301
TICKET_REPLY_STATE = 302

@rate_limit
@blacklist_check
async def support_menu_callback(update: Update, context: CallbackContext):
    """Renders support tickets list for users."""
    query = update.callback_query
    user_id = query.from_user.id if query else update.effective_user.id

    async with AsyncSessionLocal() as session:
        admin_repo = AdminRepository(session)
        tickets = await admin_repo.get_user_tickets(user_id)

        text = (
            f"{Visual.header('Support Center')}\n"
            f"Need assistance? Open a support ticket below, view your tickets, "
            f"or contact us directly on Telegram: <b>@Agen_Supporrt_bot</b>\n\n"
        )
        keyboard = []
        for ticket in tickets:
            status_emoji = "🟢" if ticket.status == "open" else "🟡" if ticket.status == "assigned" else "🔴"
            keyboard.append([InlineKeyboardButton(f"{status_emoji} #{ticket.id}: {ticket.subject}", callback_data=f"ticket:view:{ticket.id}")])

        keyboard.append([InlineKeyboardButton("➕ Open New Ticket", callback_data="ticket:create")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Main", callback_data="user_menu:main")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        if query:
            await query.edit_message_text(
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            await query.answer()
        else:
            if update.message:
                await update.message.reply_text(
                    text=text,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )

@rate_limit
@blacklist_check
async def view_ticket_callback(update: Update, context: CallbackContext):
    """Renders single support ticket details and conversation thread."""
    query = update.callback_query
    ticket_id = int(query.data.split(":")[2])
    user_id = query.from_user.id

    async with AsyncSessionLocal() as session:
        admin_repo = AdminRepository(session)
        ticket = await admin_repo.get_ticket(ticket_id)

        if not ticket or (ticket.user_id != user_id and user_id not in context.bot_data.get("admin_ids", [])):
            # If not owner and not admin
            from bot.config import settings
            if user_id not in settings.ADMIN_IDS:
                await query.answer("Access denied.", show_alert=True)
                return

        status_emoji = "🟢" if ticket.status == "open" else "🟡" if ticket.status == "assigned" else "🔴"
        text = (
            f"{Visual.header(f'Ticket #{ticket.id}')}\n"
            f"📌 <b>Subject:</b> {ticket.subject}\n"
            f"🏷 <b>Status:</b> {ticket.status.upper()} {status_emoji}\n"
            f"⚠️ <b>Priority:</b> {ticket.priority.upper()}\n"
            f"📅 <b>Created:</b> {ticket.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"{Visual.BORDER}\n"
            f"💬 <b>Conversation History:</b>\n\n"
        )

        if not ticket.messages:
            text += "<i>No messages in this ticket yet.</i>"
        else:
            for msg in ticket.messages:
                sender = "👤 You" if msg.sender_id == ticket.user_id else "🛠 Admin Support"
                text += f"<b>{sender}</b>:\n{msg.message_text}\n"
                text += f"<pre>{msg.created_at.strftime('%m-%d %H:%M')}</pre>\n\n"

        text += Visual.footer()

        keyboard = []
        if ticket.status != "closed":
            keyboard.append([InlineKeyboardButton("✍️ Reply to Ticket", callback_data=f"ticket:reply:{ticket.id}")])
            keyboard.append([InlineKeyboardButton("🔒 Close Ticket", callback_data=f"ticket:close:{ticket.id}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Support", callback_data="user_menu:support")])

        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await query.answer()

@rate_limit
@blacklist_check
async def close_ticket_callback(update: Update, context: CallbackContext):
    """Closes support ticket."""
    query = update.callback_query
    ticket_id = int(query.data.split(":")[2])

    async with AsyncSessionLocal() as session:
        admin_repo = AdminRepository(session)
        ticket = await admin_repo.get_ticket(ticket_id)
        if ticket:
            ticket.status = "closed"
            await session.commit()
            await query.answer("🔒 Ticket marked as closed.")
            await support_menu_callback(update, context)

# CREATE TICKET FSM CONVERSATION
@rate_limit
@blacklist_check
async def ticket_create_start_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    text = (
        f"{Visual.header('Open Support Ticket')}\n"
        f"✍️ Please type a short, descriptive <b>Subject</b> for your ticket (or detail your report):"
    )
    if query:
        msg = await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=UserKeyboards.back_to_main()
        )
        context.user_data["menu_msg_id"] = msg.message_id
        await query.answer()
    else:
        if update.message:
            msg = await update.message.reply_text(
                text=text,
                parse_mode="HTML",
                reply_markup=UserKeyboards.back_to_main()
            )
            context.user_data["menu_msg_id"] = msg.message_id
    return TICKET_SUBJ_STATE

async def ticket_subject_input_handler(update: Update, context: CallbackContext) -> int:
    message = update.message
    subject_text = message.text.strip()

    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    if not bot_msg_id:
        return ConversationHandler.END

    context.user_data["ticket_subject"] = subject_text

    text = (
        f"{Visual.header('Open Support Ticket')}\n"
        f"📌 Subject: <b>{subject_text}</b>\n\n"
        f"✍️ Now, please type the full <b>Message details</b> for your ticket:"
    )
    await context.bot.edit_message_text(
        chat_id=message.from_user.id,
        message_id=bot_msg_id,
        text=text,
        parse_mode="HTML",
        reply_markup=UserKeyboards.back_to_main()
    )
    return TICKET_MSG_STATE

async def ticket_message_input_handler(update: Update, context: CallbackContext) -> int:
    message = update.message
    user_id = message.from_user.id
    message_text = message.text.strip()

    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    subject = context.user_data.get("ticket_subject")

    if not bot_msg_id or not subject:
        return ConversationHandler.END

    async with AsyncSessionLocal() as session:
        admin_repo = AdminRepository(session)
        
        # Create ticket
        ticket = Ticket(user_id=user_id, subject=subject, status="open")
        await admin_repo.add(ticket)
        await session.flush() # Populate ticket id

        # Add message
        t_msg = TicketMessage(ticket_id=ticket.id, sender_id=user_id, message_text=message_text)
        await admin_repo.add(t_msg)

        await session.commit()

        text = (
            f"{Visual.header('Ticket Opened!')}\n"
            f"✅ Ticket #{ticket.id} has been successfully opened.\n"
            f"Admins have been notified. We will reply shortly!"
        )
        await context.bot.edit_message_text(
            chat_id=user_id,
            message_id=bot_msg_id,
            text=text,
            parse_mode="HTML",
            reply_markup=UserKeyboards.back_to_main()
        )

    return ConversationHandler.END

# REPLY TICKET FSM CONVERSATION
@rate_limit
@blacklist_check
async def ticket_reply_start_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    ticket_id = int(query.data.split(":")[2])
    
    text = (
        f"{Visual.header(f'Reply to Ticket #{ticket_id}')}\n"
        f"✍️ Type your reply message below:"
    )
    msg = await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=UserKeyboards.back_to_main()
    )
    context.user_data["reply_ticket_id"] = ticket_id
    context.user_data["menu_msg_id"] = msg.message_id
    return TICKET_REPLY_STATE

async def ticket_reply_input_handler(update: Update, context: CallbackContext) -> int:
    message = update.message
    user_id = message.from_user.id
    reply_text = message.text.strip()

    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    ticket_id = context.user_data.get("reply_ticket_id")

    if not bot_msg_id or not ticket_id:
        return ConversationHandler.END

    async with AsyncSessionLocal() as session:
        admin_repo = AdminRepository(session)
        ticket = await admin_repo.get_ticket(ticket_id)
        
        if ticket:
            t_msg = TicketMessage(ticket_id=ticket_id, sender_id=user_id, message_text=reply_text)
            await admin_repo.add(t_msg)
            
            # If closed, reopen it
            if ticket.status == "closed":
                ticket.status = "open"
                
            await session.commit()

            # Redraw details
            await context.bot.edit_message_text(
                chat_id=user_id,
                message_id=bot_msg_id,
                text=f"{Visual.header('Reply Sent!')}\n✅ Your reply was successfully added to Ticket #{ticket_id}.\n{Visual.footer()}",
                parse_mode="HTML",
                reply_markup=UserKeyboards.back_to_main()
            )

    return ConversationHandler.END

async def ticket_fsm_cancel_callback(update: Update, context: CallbackContext) -> int:
    await update.callback_query.answer()
    return ConversationHandler.END

ticket_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(ticket_create_start_callback, pattern="^ticket:create$"),
        CallbackQueryHandler(ticket_reply_start_callback, pattern="^ticket:reply:\\d+$"),
        MessageHandler(
            filters.Regex(r"(?i).*report.*") | (filters.COMMAND & filters.Regex(r"(?i).*report.*")),
            ticket_create_start_callback
        )
    ],
    states={
        TICKET_SUBJ_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ticket_subject_input_handler)],
        TICKET_MSG_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ticket_message_input_handler)],
        TICKET_REPLY_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ticket_reply_input_handler)]
    },
    fallbacks=[CallbackQueryHandler(ticket_fsm_cancel_callback, pattern="^user_menu:main$")],
    per_message=False
)
