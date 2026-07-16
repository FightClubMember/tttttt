import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler, MessageHandler, ConversationHandler, filters
from bot.database.connection import AsyncSessionLocal
from bot.services.market_service import MarketplaceService
from bot.repositories.agent_repo import AgentRepository
from bot.repositories.user_repo import UserRepository
from bot.repositories.admin_repo import AdminRepository
from bot.keyboards.admin_kb import AdminKeyboards
from bot.filters.admin_filter import admin_only
from bot.middlewares.blacklist import blacklist_check
from bot.middlewares.rate_limit import rate_limit
from bot.states.fsm import ADMIN_APPROVE_REWARD
from bot.utils.visual import Visual

logger = logging.getLogger(__name__)

@rate_limit
@blacklist_check
@admin_only
async def admin_categories_callback(update: Update, context: CallbackContext):
    """Lists categories for admin CRUD."""
    query = update.callback_query
    
    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        categories = await agent_repo.get_all_categories(include_hidden=True)
        
        text = f"{Visual.header('Category Management')}\nChoose a category to edit or delete:"
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=AdminKeyboards.categories_menu(categories)
        )
        await query.answer()

@rate_limit
@blacklist_check
@admin_only
async def admin_category_edit_callback(update: Update, context: CallbackContext):
    """Shows options for a specific category."""
    query = update.callback_query
    cat_id = int(query.data.split(":")[3])
    
    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        cat = await agent_repo.get_category(cat_id)
        if not cat:
            await query.answer("Category not found.", show_alert=True)
            return

        text = (
            f"{Visual.header('Edit Category')}\n"
            f"🏷 Name: <b>{cat.name}</b>\n"
            f"🎭 Icon: <code>{cat.icon}</code>\n"
            f"🖼 Banner: <code>{cat.banner_url or 'None'}</code>\n"
            f"👁 Hidden: <b>{cat.is_hidden}</b>"
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=AdminKeyboards.category_edit(cat_id)
        )
        await query.answer()

@rate_limit
@blacklist_check
@admin_only
async def admin_moderation_queue_callback(update: Update, context: CallbackContext):
    """Lists pending agent listings for review."""
    query = update.callback_query
    
    # Check if this call was made by FSM or normal query
    if not query:
        return
        
    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        pending = await agent_repo.get_pending_moderation_queue()
        
        text = f"{Visual.header('Moderation Queue')}\n"
        if not pending:
            text += "✅ All listings reviewed! Moderation queue is empty."
        else:
            text += f"There are {len(pending)} pending listings awaiting moderation:\n\n"
            
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=AdminKeyboards.moderation_queue(pending)
        )
        await query.answer()

@rate_limit
@blacklist_check
@admin_only
async def admin_inspect_agent_callback(update: Update, context: CallbackContext):
    """Inspects details of pending agent listing."""
    query = update.callback_query
    agent_id = int(query.data.split(":")[3])
    
    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        agent = await agent_repo.get_agent(agent_id)
        if not agent:
            await query.answer("Agent listing not found.", show_alert=True)
            return

        text = (
            f"{Visual.header('Inspect Submission')}\n"
            f"📦 Name/ID: <b>{agent.name}</b>\n"
            f"👤 Seller ID: <code>{agent.seller_id}</code>\n\n"
            f"📝 <b>Description:</b>\n{agent.description}\n\n"
            f"🚀 <b>Features:</b>\n{agent.features or 'None'}\n\n"
            f"📂 <b>Proof File ID:</b> <code>{agent.file_id}</code>"
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=AdminKeyboards.moderation_inspect(agent_id)
        )
        await query.answer()

@rate_limit
@blacklist_check
@admin_only
async def admin_approve_agent_callback(update: Update, context: CallbackContext) -> int:
    """Triggered on Approve click. Enters FSM to ask for custom credit reward."""
    query = update.callback_query
    agent_id = int(query.data.split(":")[3])
    
    context.user_data["moderation_approve_agent_id"] = agent_id
    context.user_data["menu_msg_id"] = query.message.message_id
    
    text = (
        f"{Visual.header('Approve Submission')}\n"
        f"💰 Please type the <b>credit reward amount</b> to give to the seller for this bot:"
    )
    await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚫 Cancel", callback_data="admin:moderation:cancel")]])
    )
    await query.answer()
    return ADMIN_APPROVE_REWARD

async def admin_approve_reward_handler(update: Update, context: CallbackContext) -> int:
    """Processes typed reward amount, credits seller, and publishes agent."""
    message = update.message
    admin_id = message.from_user.id
    
    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    if not bot_msg_id:
        return ConversationHandler.END

    reward_text = message.text.strip()
    try:
        reward_amount = float(reward_text)
        if reward_amount < 0:
            raise ValueError()
    except ValueError:
        await context.bot.edit_message_text(
            chat_id=admin_id,
            message_id=bot_msg_id,
            text="⚠️ Invalid reward. Please type a positive numeric credit value:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚫 Cancel", callback_data="admin:moderation:cancel")]])
        )
        return ADMIN_APPROVE_REWARD

    agent_id = context.user_data.get("moderation_approve_agent_id")
    if not agent_id:
        return ConversationHandler.END

    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        agent = await agent_repo.get_agent(agent_id)
        if not agent:
            await context.bot.edit_message_text(
                chat_id=admin_id,
                message_id=bot_msg_id,
                text="❌ Agent submission not found.",
                reply_markup=AdminKeyboards.back_to_dash()
            )
            return ConversationHandler.END

        # Approve and publish agent listing
        agent.status = "active"
        
        # Credit seller user
        user_repo = UserRepository(session)
        seller = await user_repo.get_user(agent.seller_id)
        if seller:
            seller.credits += reward_amount
            seller.lifetime_earned += reward_amount
            
            # Send notification update
            admin_repo = AdminRepository(session)
            await admin_repo.add_notification(
                agent.seller_id,
                f"✅ Your bot submission (ID: {agent.name}) was approved! Granting +{reward_amount} Credits to your balance."
            )
            
        await session.commit()

    text = (
        f"{Visual.header('Approval Complete')}\n"
        f"✅ <b>Listing approved successfully!</b>\n\n"
        f"Granted <b>+{reward_amount} Credits</b> to Seller (ID: {agent.seller_id})."
    )
    
    await context.bot.edit_message_text(
        chat_id=admin_id,
        message_id=bot_msg_id,
        text=text,
        parse_mode="HTML",
        reply_markup=AdminKeyboards.back_to_dash()
    )
    return ConversationHandler.END

@rate_limit
@blacklist_check
@admin_only
async def admin_moderation_cancel_callback(update: Update, context: CallbackContext) -> int:
    """Cancels approval and returns to moderation queue."""
    query = update.callback_query
    await query.answer("Approval cancelled.")
    
    # Simulated query update to redraw
    await admin_moderation_queue_callback(update, context)
    return ConversationHandler.END

@rate_limit
@blacklist_check
@admin_only
async def admin_reject_agent_callback(update: Update, context: CallbackContext):
    """Rejects pending agent listing."""
    query = update.callback_query
    agent_id = int(query.data.split(":")[3])
    
    async with AsyncSessionLocal() as session:
        market_service = MarketplaceService(session)
        success = await market_service.reject_agent(agent_id)
        if success:
            await query.answer("❌ Listing rejected.")
        else:
            await query.answer("❌ Error rejecting listing.", show_alert=True)
            
        # Redraw queue
        await admin_moderation_queue_callback(update, context)

# Admin approval conversation FSM
admin_moderation_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(admin_approve_agent_callback, pattern="^admin:moderation:approve:\d+$")],
    states={
        ADMIN_APPROVE_REWARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_approve_reward_handler)]
    },
    fallbacks=[CallbackQueryHandler(admin_moderation_cancel_callback, pattern="^admin:moderation:cancel$")],
    per_message=False
)
