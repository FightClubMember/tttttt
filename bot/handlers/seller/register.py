import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler, MessageHandler, ConversationHandler, filters
from bot.database.connection import AsyncSessionLocal
from bot.repositories.agent_repo import AgentRepository
from bot.models.agent import Agent, Category
from bot.keyboards.seller_kb import SellerKeyboards
from bot.keyboards.user_kb import UserKeyboards
from bot.middlewares.blacklist import blacklist_check
from bot.middlewares.rate_limit import rate_limit
from bot.states.fsm import SELL_NAME, SELL_FILE, SELL_PRICE
from bot.utils.visual import Visual
from bot.config import settings

logger = logging.getLogger(__name__)

@rate_limit
@blacklist_check
async def seller_register_start_callback(update: Update, context: CallbackContext) -> int:
    """Entry point for submitting an agent listing."""
    query = update.callback_query
    
    # Initialize user_data states
    context.user_data["sell_form"] = {}

    text = (
        f"{Visual.header('Sell Your Agent')}\n"
        f"Step 1: 📦 Please type the <b>Agent ID or Number</b>:"
    )
    
    if query:
        msg = await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=SellerKeyboards.cancel_submission()
        )
        context.user_data["menu_msg_id"] = msg.message_id
        await query.answer()
    else:
        msg = await update.message.reply_text(
            text=text,
            parse_mode="HTML",
            reply_markup=SellerKeyboards.cancel_submission()
        )
        context.user_data["menu_msg_id"] = msg.message_id
        
    return SELL_NAME

async def name_input_handler(update: Update, context: CallbackContext) -> int:
    """Handles Agent ID/Number text input."""
    message = update.message
    name = message.text.strip()
    
    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    if not bot_msg_id:
        return ConversationHandler.END

    context.user_data["sell_form"]["name"] = name

    text = (
        f"{Visual.header('Sell Your Agent')}\n"
        f"📦 Agent ID: <b>{name}</b>\n\n"
        f"Step 2: 📂 Please upload **Proof of Ownership** (source code ZIP, setup files, or screenshots/photos):"
    )
    
    await context.bot.edit_message_text(
        chat_id=message.from_user.id,
        message_id=bot_msg_id,
        text=text,
        parse_mode="HTML",
        reply_markup=SellerKeyboards.cancel_submission()
    )
    return SELL_FILE

async def file_input_handler(update: Update, context: CallbackContext) -> int:
    """Handles Proof file/document/photo submission and registers the agent."""
    message = update.message
    user_id = message.from_user.id
    doc = message.document
    photo = message.photo
    
    file_id = None
    if doc:
        file_id = doc.file_id
    elif photo:
        file_id = photo[-1].file_id

    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    if not bot_msg_id:
        return ConversationHandler.END

    if not file_id:
        await context.bot.edit_message_text(
            chat_id=user_id,
            message_id=bot_msg_id,
            text="⚠️ Invalid proof. Please upload a source code ZIP archive or screenshots:",
            reply_markup=SellerKeyboards.cancel_submission()
        )
        return SELL_FILE

    context.user_data["sell_form"]["file_id"] = file_id

    # If the user is an admin, let them set the price directly
    if user_id in settings.ADMIN_IDS:
        text = (
            f"{Visual.header('Admin Agent Upload')}\n"
            f"📦 Agent ID: <b>{context.user_data['sell_form']['name']}</b>\n\n"
            f"💰 Please type the <b>purchase price (credits)</b> for this listing in the marketplace:"
        )
        await context.bot.edit_message_text(
            chat_id=user_id,
            message_id=bot_msg_id,
            text=text,
            parse_mode="HTML",
            reply_markup=SellerKeyboards.cancel_submission()
        )
        return SELL_PRICE

    name = context.user_data["sell_form"]["name"]

    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        
        # Ensure a default category exists
        cats = await agent_repo.get_all_categories(include_hidden=True)
        if cats:
            cat_id = cats[0].id
        else:
            new_cat = Category(name="General", icon="🤖")
            await agent_repo.add(new_cat)
            await session.commit()
            cat_id = new_cat.id

        # Create pending agent submission
        new_agent = Agent(
            seller_id=user_id,
            category_id=cat_id,
            name=name,
            description="Seller bot submission (Awaiting approval)",
            version="1.0",
            price=0.0,  # Credit reward is assigned by the admin on approval
            file_id=file_id,
            features="Proof Submitted",
            status="pending"
        )
        await agent_repo.add(new_agent)
        await session.commit()

    text = (
        f"{Visual.header('Submission Complete')}\n"
        f"✅ <b>Your bot has been successfully submitted!</b>\n\n"
        f"Status: <code>Waiting for admin check and confirm</code>\n\n"
        f"Once the admin verifies your proof, they will confirm the submission and credit your wallet."
    )
    
    await context.bot.edit_message_text(
        chat_id=user_id,
        message_id=bot_msg_id,
        text=text,
        parse_mode="HTML",
        reply_markup=UserKeyboards.back_to_main()
    )
    
    return ConversationHandler.END

async def price_input_handler(update: Update, context: CallbackContext) -> int:
    """Handles admin setting the price directly and publishes the bot."""
    message = update.message
    user_id = message.from_user.id
    price_text = message.text.strip()

    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    if not bot_msg_id:
        return ConversationHandler.END

    try:
        price = float(price_text)
        if price < 0:
            raise ValueError()
    except ValueError:
        await context.bot.edit_message_text(
            chat_id=user_id,
            message_id=bot_msg_id,
            text="⚠️ Invalid price. Please type a positive numeric credit value:",
            reply_markup=SellerKeyboards.cancel_submission()
        )
        return SELL_PRICE

    name = context.user_data["sell_form"]["name"]
    file_id = context.user_data["sell_form"]["file_id"]

    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        
        # Ensure a default category exists
        cats = await agent_repo.get_all_categories(include_hidden=True)
        if cats:
            cat_id = cats[0].id
        else:
            new_cat = Category(name="General", icon="🤖")
            await agent_repo.add(new_cat)
            await session.commit()
            cat_id = new_cat.id

        # Publish listing directly
        new_agent = Agent(
            seller_id=user_id,
            category_id=cat_id,
            name=name,
            description="Official Agent Listing",
            version="1.0",
            price=price,
            file_id=file_id,
            features="Direct Upload",
            status="active"
        )
        await agent_repo.add(new_agent)
        await session.commit()

    text = (
        f"{Visual.header('Agent Published')}\n"
        f"✅ <b>Your bot has been successfully published directly!</b>\n\n"
        f"Name: <b>{name}</b>\n"
        f"Price: <b>{price} Credits</b>\n"
        f"Status: <code>Active & Published</code>"
    )
    
    await context.bot.edit_message_text(
        chat_id=user_id,
        message_id=bot_msg_id,
        text=text,
        parse_mode="HTML",
        reply_markup=UserKeyboards.back_to_main()
    )
    return ConversationHandler.END

@rate_limit
@blacklist_check
async def cancel_sell_callback(update: Update, context: CallbackContext) -> int:
    """Cancels FSM and returns to dashboard."""
    query = update.callback_query
    await query.answer("Submission cancelled.")
    
    async with AsyncSessionLocal() as session:
        from bot.handlers.user.base import show_main_menu
        await show_main_menu(update, context, session, query.from_user.id, query.from_user.first_name, edit=True)
        
    return ConversationHandler.END

# Seller registration FSM ConversationHandler
seller_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(seller_register_start_callback, pattern="^user_menu:sell$"),
        MessageHandler(
            filters.Regex(r"(?i).*sell agent.*") | (filters.COMMAND & filters.Regex(r"(?i).*sell.*")),
            seller_register_start_callback
        )
    ],
    states={
        SELL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_input_handler)],
        SELL_FILE: [MessageHandler((filters.Document.ALL | filters.PHOTO) & ~filters.COMMAND, file_input_handler)],
        SELL_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_input_handler)]
    },
    fallbacks=[CallbackQueryHandler(cancel_sell_callback, pattern="^sell:cancel$")],
    per_message=False
)
