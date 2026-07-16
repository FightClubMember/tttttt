import logging
from telegram import Update
from telegram.ext import CallbackContext, CallbackQueryHandler
from bot.database.connection import AsyncSessionLocal
from bot.keyboards.admin_kb import AdminKeyboards
from bot.repositories.user_repo import UserRepository
from bot.repositories.agent_repo import AgentRepository
from bot.repositories.admin_repo import AdminRepository
from bot.filters.admin_filter import admin_only
from bot.middlewares.blacklist import blacklist_check
from bot.middlewares.rate_limit import rate_limit
from bot.utils.visual import Visual

logger = logging.getLogger(__name__)

@rate_limit
@blacklist_check
@admin_only
async def admin_dashboard_callback(update: Update, context: CallbackContext):
    """Renders the advanced Admin Panel control dashboard."""
    query = update.callback_query
    
    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        agent_repo = AgentRepository(session)
        admin_repo = AdminRepository(session)

        # Retrieve statistics summary
        users = await user_repo.get_all_users()
        categories = await agent_repo.get_all_categories(include_hidden=True)
        mod_queue = await agent_repo.get_pending_moderation_queue()
        
        # Calculate credits summary
        total_issued = sum(u.lifetime_earned for u in users)
        total_spent = sum(u.lifetime_spent for u in users)

        text = (
            f"{Visual.header('Admin Dashboard', 'Management Console')}\n"
            f"👥 Total Users: <b>{len(users)}</b>\n"
            f"📂 Categories: <b>{len(categories)}</b>\n"
            f"📦 Pending moderation: <b>{len(mod_queue)} agents</b>\n\n"
            f"💰 Total Credits Issued: <b>{total_issued:.1f}</b>\n"
            f"💸 Total Credits Spent: <b>{total_spent:.1f}</b>\n\n"
            f"Select a module from the options below to configure system data."
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=AdminKeyboards.dashboard()
        )
        await query.answer()

@rate_limit
@blacklist_check
@admin_only
async def stats_view_callback(update: Update, context: CallbackContext):
    """Renders expanded analytics charts data."""
    query = update.callback_query
    
    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        agent_repo = AgentRepository(session)

        users = await user_repo.get_all_users()
        active_users = sum(1 for u in users if u.role != "user")
        
        # Calculate most sold agents
        from sqlalchemy import select, func
        from bot.models.agent import OrderItem, Agent
        stmt = (
            select(Agent.name, func.count(OrderItem.id))
            .join(OrderItem)
            .group_by(Agent.id)
            .order_by(func.count(OrderItem.id).desc())
            .limit(3)
        )
        res = await session.execute(stmt)
        top_agents = res.all()

        text = (
            f"{Visual.header('Marketplace Analytics', 'Statistics Overview')}\n"
            f"👤 Registered accounts: <b>{len(users)}</b>\n"
            f"🛡 Admins & Sellers: <b>{active_users}</b>\n\n"
            f"🏆 <b>Best-Selling Agents:</b>\n"
        )
        if not top_agents:
            text += "<i>No sales completed yet.</i>"
        else:
            for idx, (name, count) in enumerate(top_agents, 1):
                text += f" {idx}. {name} — <b>{count} downloads</b>\n"

        text += Visual.footer()
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=AdminKeyboards.back_to_dash()
        )
        await query.answer()

@rate_limit
@blacklist_check
@admin_only
async def admin_close_callback(update: Update, context: CallbackContext):
    """Closes admin panel and returns user to the main menu."""
    query = update.callback_query
    
    from bot.handlers.user.base import show_main_menu
    async with AsyncSessionLocal() as session:
        await show_main_menu(update, context, session, query.from_user.id, query.from_user.first_name, edit=True)
    await query.answer()
