import logging
from telegram import Update
from telegram.ext import CallbackContext, CallbackQueryHandler, MessageHandler, ConversationHandler, filters
from bot.database.connection import AsyncSessionLocal
from bot.services.market_service import MarketplaceService
from bot.repositories.agent_repo import AgentRepository
from bot.repositories.user_repo import UserRepository
from bot.keyboards.user_kb import UserKeyboards
from bot.middlewares.blacklist import blacklist_check
from bot.middlewares.rate_limit import rate_limit
from bot.utils.visual import Visual

logger = logging.getLogger(__name__)

# FSM states
SEARCH_INPUT_STATE = 601
REVIEW_INPUT_STATE = 602

@rate_limit
@blacklist_check
async def categories_list_callback(update: Update, context: CallbackContext):
    """Renders the categories list."""
    query = update.callback_query
    
    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        categories = await agent_repo.get_all_categories(include_hidden=False)
        
        text = (
            f"{Visual.header('Marketplace Catalog')}\n"
            f"Select a category below to explore premium digital agents:"
        )
        reply_markup = UserKeyboards.categories_list(categories)
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
async def category_agents_callback(update: Update, context: CallbackContext):
    """Renders agents in a specific category."""
    query = update.callback_query
    category_id = int(query.data.split(":")[2])
    
    # Store category_id in user_data for navigation back
    context.user_data["current_cat_id"] = category_id

    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        category = await agent_repo.get_category(category_id)
        if not category:
            await query.answer("Category not found.", show_alert=True)
            return
            
        agents = await agent_repo.get_agents_by_category(category_id, include_hidden=False)

        text = (
            f"{Visual.header(f'{category.icon} {category.name}')}\n"
            f"Here are the available premium agents in this category:\n\n"
        )
        if not agents:
            text += "⚠️ No agents listed in this category yet. Check back later!"
            
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=UserKeyboards.agents_list(agents, category_id)
        )
        await query.answer()

@rate_limit
@blacklist_check
async def agent_details_callback(update: Update, context: CallbackContext):
    """Renders details of a single agent listing."""
    query = update.callback_query
    agent_id = int(query.data.split(":")[2])
    user_id = query.from_user.id

    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        agent = await agent_repo.get_agent(agent_id)
        if not agent or agent.status != "active":
            await query.answer("Agent not found or inactive.", show_alert=True)
            return

        is_fav = await agent_repo.is_favorite(user_id, agent_id)
        is_wl = await agent_repo.is_in_wishlist(user_id, agent_id)
        
        # Load seller name
        user_repo = UserRepository(session)
        seller = await user_repo.get_user(agent.seller_id)
        seller_name = seller.first_name if seller else "Unknown Seller"

        features_list = agent.features.split(",") if agent.features else []
        features_str = "\n".join(f"   • {f.strip()}" for f in features_list if f.strip())

        text = (
            f"{Visual.header('Agent Details')}\n"
            f"📦 <b>Name:</b> {agent.name}\n"
            f"🏷 <b>Version:</b> v{agent.version}\n"
            f"💰 <b>Price:</b> <b>{agent.price} Credits</b>\n"
            f"👤 <b>Seller:</b> {seller_name}\n"
            f"⭐ <b>Rating:</b> {agent.rating} / 5.0\n"
            f"📥 <b>Downloads:</b> {agent.downloads}\n"
            f"📦 <b>Stock:</b> {'Unlimited' if agent.stock == -1 else agent.stock}\n\n"
            f"📝 <b>Description:</b>\n{agent.description}\n\n"
        )
        if features_str:
            text += f"🚀 <b>Features:</b>\n{features_str}\n\n"
            
        if agent.demo_url:
            text += f"🌐 <b>Live Demo:</b> {agent.demo_url}\n\n"

        text += Visual.footer()

        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=UserKeyboards.agent_details(agent_id, is_fav, is_wl)
        )
        await query.answer()

@rate_limit
@blacklist_check
async def agent_terms_callback(update: Update, context: CallbackContext):
    """Shows pre-checkout Terms & Conditions acceptance screen."""
    query = update.callback_query
    agent_id = int(query.data.split(":")[2])
    
    async with AsyncSessionLocal() as session:
        from bot.repositories.admin_repo import AdminRepository
        admin_repo = AdminRepository(session)
        terms = await admin_repo.get_setting("terms_and_conditions")
        if not terms:
            terms = (
                "<b>Money Agent Marketplace Terms of Service</b>\n\n"
                "1. All purchases are final. No refunds will be provided after files are delivered.\n"
                "2. Redistribution, resale, or sublicensing of purchased agent codes is strictly prohibited.\n"
                "3. We do not guarantee compatibility with all external systems. Please run tests carefully."
            )
            
        text = (
            f"{Visual.header('Terms & Conditions')}\n"
            f"{terms}\n\n"
            f"⚠️ <b>By proceeding, you explicitly agree to the above terms and conditions.</b>"
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=UserKeyboards.terms_and_conditions(agent_id)
        )
        await query.answer()

@rate_limit
@blacklist_check
async def buy_agent_callback(update: Update, context: CallbackContext):
    """Processes credit purchases transactions for agents."""
    query = update.callback_query
    agent_id = int(query.data.split(":")[2])
    user_id = query.from_user.id

    async with AsyncSessionLocal() as session:
        market_service = MarketplaceService(session)
        success, message, order = await market_service.purchase_agent(user_id, agent_id)

        if not success:
            await query.answer(message, show_alert=True)
            return

        # Transaction success visual card
        agent = await market_service.agent_repo.get_agent(agent_id)
        text = (
            f"{Visual.header('Purchase Successful!')}\n"
            f"🎉 You successfully bought <b>{agent.name}</b>!\n"
            f"💸 Price paid: <b>{agent.price} Credits</b>\n\n"
            f"You can now download the agent files below."
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=UserKeyboards.download_agent(agent.file_id, agent.id)
        )
        await query.answer("🛒 Purchased successfully!")

@rate_limit
@blacklist_check
async def download_file_callback(update: Update, context: CallbackContext):
    """Delivers purchased agent files directly in chat."""
    query = update.callback_query
    agent_id = int(query.data.split(":")[2])
    user_id = query.from_user.id

    await query.answer("📥 Preparing files download link...")

    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        # Check if they own the order
        orders = await agent_repo.get_user_orders(user_id)
        owns_item = False
        target_agent = None
        for order in orders:
            for item in order.items:
                if item.agent_id == agent_id:
                    owns_item = True
                    target_agent = item.agent
                    break
            if owns_item:
                break

        if not owns_item or not target_agent:
            await query.answer("❌ You haven't purchased this agent yet.", show_alert=True)
            return

        # Deliver file using telegram file_id
        await context.bot.send_document(
            chat_id=user_id,
            document=target_agent.file_id,
            filename=f"{target_agent.name.replace(' ', '_')}_v{target_agent.version}.zip",
            caption=f"📦 <b>{target_agent.name} v{target_agent.version}</b>\n\nHere are your files! Thank you for purchasing from our marketplace.",
            parse_mode="HTML",
            reply_markup=UserKeyboards.back_to_main()
        )

# FAVORITES AND WISHLISTS DYNAMICS
@rate_limit
@blacklist_check
async def toggle_fav_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    agent_id = int(query.data.split(":")[2])
    user_id = query.from_user.id

    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        is_fav = await agent_repo.is_favorite(user_id, agent_id)
        if is_fav:
            await agent_repo.remove_favorite(user_id, agent_id)
            await query.answer("⭐ Removed from Favorites!")
        else:
            await agent_repo.add_favorite(user_id, agent_id)
            await query.answer("⭐ Added to Favorites!")
            
        await session.commit()
        # Redraw detail page
        await agent_details_callback(update, context)

@rate_limit
@blacklist_check
async def toggle_wl_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    agent_id = int(query.data.split(":")[2])
    user_id = query.from_user.id

    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        is_wl = await agent_repo.is_in_wishlist(user_id, agent_id)
        if is_wl:
            await agent_repo.remove_from_wishlist(user_id, agent_id)
            await query.answer("❤️ Removed from Wishlist!")
        else:
            await agent_repo.add_to_wishlist(user_id, agent_id)
            await query.answer("❤️ Added to Wishlist!")
            
        await session.commit()
        await agent_details_callback(update, context)

@rate_limit
@blacklist_check
async def view_favorites_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id

    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        favs = await agent_repo.get_favorites(user_id)

        text = f"{Visual.header('Your Favorites')}\n"
        if not favs:
            text += "⭐ You haven't added any agents to your favorites list yet."
        else:
            text += "Explore your bookmarked favorites:\n\n"
            
        keyboard = []
        for agent in favs:
            keyboard.append([InlineKeyboardButton(f"⭐ {agent.name} ({agent.price} Credits)", callback_data=f"catalog:agent:{agent.id}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Main", callback_data="user_menu:main")])
        
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await query.answer()

@rate_limit
@blacklist_check
async def view_wishlist_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id

    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        wls = await agent_repo.get_wishlist(user_id)

        text = f"{Visual.header('Your Wishlist')}\n"
        if not wls:
            text += "❤️ Your wishlist is empty. Bookmark agents to purchase them later!"
        else:
            text += "Explore your saved wishlist:\n\n"
            
        keyboard = []
        for agent in wls:
            keyboard.append([InlineKeyboardButton(f"❤️ {agent.name} ({agent.price} Credits)", callback_data=f"catalog:agent:{agent.id}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Main", callback_data="user_menu:main")])
        
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await query.answer()

# CATALOG SEARCH CONVERSATION FSM
@rate_limit
@blacklist_check
async def search_start_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    text = (
        f"{Visual.header('Search Catalog')}\n"
        f"🔍 Type your search keywords below (matches agent name or description):"
    )
    msg = await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=UserKeyboards.back_to_main()
    )
    context.user_data["menu_msg_id"] = msg.message_id
    return SEARCH_INPUT_STATE

async def search_input_handler(update: Update, context: CallbackContext) -> int:
    message = update.message
    user_id = message.from_user.id
    query_text = message.text.strip()

    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    if not bot_msg_id:
        return ConversationHandler.END

    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        results = await agent_repo.search_agents(query_text)

        text = (
            f"{Visual.header('Search Results')}\n"
            f"🔍 Keywords: '<i>{query_text}</i>'\n\n"
        )
        if not results:
            text += "❌ No agents match your search terms."
        else:
            text += f"Found {len(results)} matching agents:\n\n"

        keyboard = []
        for agent in results:
            keyboard.append([InlineKeyboardButton(f"📦 {agent.name} — {agent.price} Cr", callback_data=f"catalog:agent:{agent.id}")])
        keyboard.append([InlineKeyboardButton("🔙 Catalog Categories", callback_data="user_menu:buy")])

        await context.bot.edit_message_text(
            chat_id=user_id,
            message_id=bot_msg_id,
            text=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    return ConversationHandler.END

# CATALOG RATING / STARS REVIEW FLOW
@rate_limit
@blacklist_check
async def rate_stars_callback(update: Update, context: CallbackContext):
    """Saves numeric rating stars and triggers text review FSM."""
    query = update.callback_query
    parts = query.data.split(":")
    agent_id = int(parts[2])
    stars = int(parts[3])
    user_id = query.from_user.id

    context.user_data["review_agent_id"] = agent_id
    context.user_data["review_stars"] = stars

    # Query matching order
    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        orders = await agent_repo.get_user_orders(user_id)
        target_order = None
        for order in orders:
            for item in order.items:
                if item.agent_id == agent_id:
                    target_order = order
                    break
            if target_order:
                break
                
        if not target_order:
            await query.answer("❌ Order record not found.", show_alert=True)
            return

        context.user_data["review_order_id"] = target_order.id

    # Prompt text review
    text = (
        f"{Visual.header('Submit Review')}\n"
        f"⭐ Stars Given: <b>{'★' * stars}</b>\n\n"
        f"📝 Please write a short comment about this agent. Type it below:"
    )
    msg = await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=UserKeyboards.back_to_main()
    )
    context.user_data["menu_msg_id"] = msg.message_id
    # Run FSM state transition
    return REVIEW_INPUT_STATE

async def review_input_handler(update: Update, context: CallbackContext) -> int:
    message = update.message
    user_id = message.from_user.id
    review_text = message.text.strip()

    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    agent_id = context.user_data.get("review_agent_id")
    stars = context.user_data.get("review_stars")
    order_id = context.user_data.get("review_order_id")

    if not bot_msg_id or not agent_id or not stars or not order_id:
        return ConversationHandler.END

    async with AsyncSessionLocal() as session:
        market_service = MarketplaceService(session)
        success, feedback = await market_service.submit_review(user_id, order_id, agent_id, stars, review_text)

        await context.bot.edit_message_text(
            chat_id=user_id,
            message_id=bot_msg_id,
            text=f"{Visual.header('Submit Review')}\n{feedback}\n{Visual.footer()}",
            parse_mode="HTML",
            reply_markup=UserKeyboards.back_to_main()
        )

    return ConversationHandler.END

async def review_cancel_callback(update: Update, context: CallbackContext) -> int:
    await update.callback_query.answer()
    return ConversationHandler.END

search_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(search_start_callback, pattern="^catalog:search$")],
    states={
        SEARCH_INPUT_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_input_handler)]
    },
    fallbacks=[CallbackQueryHandler(review_cancel_callback, pattern="^user_menu:main$")],
    per_message=False
)

review_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(rate_stars_callback, pattern="^catalog:rate:\\d+:\\d+$")],
    states={
        REVIEW_INPUT_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, review_input_handler)]
    },
    fallbacks=[CallbackQueryHandler(review_cancel_callback, pattern="^user_menu:main$")],
    per_message=False
)
