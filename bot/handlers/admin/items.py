import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler
from bot.database.connection import AsyncSessionLocal
from bot.services.market_service import MarketplaceService
from bot.repositories.agent_repo import AgentRepository
from bot.keyboards.admin_kb import AdminKeyboards
from bot.filters.admin_filter import admin_only
from bot.middlewares.blacklist import blacklist_check
from bot.middlewares.rate_limit import rate_limit
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
    """Inspec details of pending agent listing."""
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
            f"📦 Name: <b>{agent.name}</b>\n"
            f"💰 Price: <b>{agent.price} Credits</b>\n"
            f"👤 Seller ID: <code>{agent.seller_id}</code>\n\n"
            f"📝 <b>Description:</b>\n{agent.description}\n\n"
            f"🚀 <b>Features:</b>\n{agent.features or 'None'}\n\n"
            f"🌐 <b>Demo URL:</b> {agent.demo_url or 'None'}\n"
            f"📓 <b>Seller notes:</b> {agent.extra_notes or 'None'}"
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
async def admin_approve_agent_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    agent_id = int(query.data.split(":")[3])
    
    async with AsyncSessionLocal() as session:
        market_service = MarketplaceService(session)
        success = await market_service.approve_agent(agent_id)
        if success:
            await query.answer("✅ Listing approved and published!")
        else:
            await query.answer("❌ Error approving listing.", show_alert=True)
            
        # Redraw queue
        await admin_moderation_queue_callback(update, context)

@rate_limit
@blacklist_check
@admin_only
async def admin_reject_agent_callback(update: Update, context: CallbackContext):
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
