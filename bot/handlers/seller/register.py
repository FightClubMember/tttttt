import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler, MessageHandler, ConversationHandler, filters
from bot.database.connection import AsyncSessionLocal
from bot.repositories.agent_repo import AgentRepository
from bot.services.market_service import MarketplaceService
from bot.keyboards.seller_kb import SellerKeyboards
from bot.keyboards.user_kb import UserKeyboards
from bot.middlewares.blacklist import blacklist_check
from bot.middlewares.rate_limit import rate_limit
from bot.states.fsm import *
from bot.utils.visual import Visual

logger = logging.getLogger(__name__)

@rate_limit
@blacklist_check
async def sell_agent_start_callback(update: Update, context: CallbackContext) -> int:
    """Entry point for submitting an agent listing."""
    query = update.callback_query
    user_id = query.from_user.id

    # Initialize user_data states
    context.user_data["sell_form"] = {}
    context.user_data["sell_screenshots"] = []

    text = (
        f"{Visual.header('Sell Your Agent')}\n"
        f"Step 1: 📦 Please type the <b>Agent Name</b>:"
    )
    msg = await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=SellerKeyboards.cancel_submission()
    )
    context.user_data["menu_msg_id"] = msg.message_id
    return SELL_NAME

async def name_input_handler(update: Update, context: CallbackContext) -> int:
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

    # Next step: Category selection
    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        categories = await agent_repo.get_all_categories(include_hidden=False)

        text = (
            f"{Visual.header('Sell Your Agent')}\n"
            f"📦 Name: <b>{name}</b>\n\n"
            f"Step 2: 📂 Select the <b>Category</b> below:"
        )
        await context.bot.edit_message_text(
            chat_id=message.from_user.id,
            message_id=bot_msg_id,
            text=text,
            parse_mode="HTML",
            reply_markup=SellerKeyboards.category_select(categories)
        )
    return SELL_CATEGORY

async def category_select_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    category_id = int(query.data.split(":")[2])
    context.user_data["sell_form"]["category_id"] = category_id

    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        cat = await agent_repo.get_category(category_id)
        cat_name = f"{cat.icon} {cat.name}" if cat else f"ID: {category_id}"

    context.user_data["sell_form"]["cat_name"] = cat_name

    text = (
        f"{Visual.header('Sell Your Agent')}\n"
        f"📦 Name: <b>{context.user_data['sell_form']['name']}</b>\n"
        f"📂 Category: <b>{cat_name}</b>\n\n"
        f"Step 3: 📝 Type a full, compelling <b>Description</b> for the agent listing:"
    )
    await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=SellerKeyboards.cancel_submission()
    )
    await query.answer()
    return SELL_DESCRIPTION

async def description_input_handler(update: Update, context: CallbackContext) -> int:
    message = update.message
    desc = message.text.strip()
    
    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    if not bot_msg_id:
        return ConversationHandler.END

    context.user_data["sell_form"]["description"] = desc

    text = (
        f"{Visual.header('Sell Your Agent')}\n"
        f"📦 Name: <b>{context.user_data['sell_form']['name']}</b>\n\n"
        f"Step 4: 🚀 Type a list of key <b>Features</b> (comma-separated):"
    )
    await context.bot.edit_message_text(
        chat_id=message.from_user.id,
        message_id=bot_msg_id,
        text=text,
        parse_mode="HTML",
        reply_markup=SellerKeyboards.cancel_submission()
    )
    return SELL_FEATURES

async def features_input_handler(update: Update, context: CallbackContext) -> int:
    message = update.message
    feats = message.text.strip()
    
    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    if not bot_msg_id:
        return ConversationHandler.END

    context.user_data["sell_form"]["features"] = feats

    text = (
        f"{Visual.header('Sell Your Agent')}\n"
        f"📦 Name: <b>{context.user_data['sell_form']['name']}</b>\n\n"
        f"Step 5: 💰 Enter the <b>Price</b> in Credits (positive number):"
    )
    await context.bot.edit_message_text(
        chat_id=message.from_user.id,
        message_id=bot_msg_id,
        text=text,
        parse_mode="HTML",
        reply_markup=SellerKeyboards.cancel_submission()
    )
    return SELL_PRICE

async def price_input_handler(update: Update, context: CallbackContext) -> int:
    message = update.message
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
        if price <= 0:
            raise ValueError()
    except ValueError:
        # Reprompt on invalid price
        await context.bot.edit_message_text(
            chat_id=message.from_user.id,
            message_id=bot_msg_id,
            text=f"⚠️ Invalid price. Please enter a valid positive number for Credits cost:",
            reply_markup=SellerKeyboards.cancel_submission()
        )
        return SELL_PRICE

    context.user_data["sell_form"]["price"] = price

    text = (
        f"{Visual.header('Sell Your Agent')}\n"
        f"📦 Name: <b>{context.user_data['sell_form']['name']}</b>\n"
        f"💰 Price: <b>{price} Credits</b>\n\n"
        f"Step 6: 🌐 Enter a <b>Live Demo Link</b> (e.g. website, demo bot link) or skip:"
    )
    await context.bot.edit_message_text(
        chat_id=message.from_user.id,
        message_id=bot_msg_id,
        text=text,
        parse_mode="HTML",
        reply_markup=SellerKeyboards.skipped_field("Demo")
    )
    return SELL_DEMO

async def demo_input_handler(update: Update, context: CallbackContext) -> int:
    message = update.message
    demo = message.text.strip()
    
    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    if not bot_msg_id:
        return ConversationHandler.END

    context.user_data["sell_form"]["demo_url"] = demo
    return await prompt_for_file(message.from_user.id, bot_msg_id, context)

async def skip_demo_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    context.user_data["sell_form"]["demo_url"] = None
    await query.answer()
    return await prompt_for_file(query.from_user.id, query.message.message_id, context)

async def prompt_for_file(chat_id: int, bot_msg_id: int, context: CallbackContext) -> int:
    text = (
        f"{Visual.header('Sell Your Agent')}\n"
        f"📦 Name: <b>{context.user_data['sell_form']['name']}</b>\n\n"
        f"Step 7: 📤 Please <b>Upload the Agent File</b> (compress as a .zip or .rar document):"
    )
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=bot_msg_id,
        text=text,
        parse_mode="HTML",
        reply_markup=SellerKeyboards.cancel_submission()
    )
    return SELL_FILE

async def file_input_handler(update: Update, context: CallbackContext) -> int:
    message = update.message
    doc = message.document
    
    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    if not bot_msg_id:
        return ConversationHandler.END

    if not doc:
        # Reprompt if not a document
        await context.bot.edit_message_text(
            chat_id=message.from_user.id,
            message_id=bot_msg_id,
            text="⚠️ You must send a document file (.zip, .rar, etc.):",
            reply_markup=SellerKeyboards.cancel_submission()
        )
        return SELL_FILE

    context.user_data["sell_form"]["file_id"] = doc.file_id

    text = (
        f"{Visual.header('Sell Your Agent')}\n"
        f"📦 Name: <b>{context.user_data['sell_form']['name']}</b>\n\n"
        f"Step 8: 🖼 Send up to 3 <b>Screenshots</b> of the agent (send images one-by-one or skip):"
    )
    await context.bot.edit_message_text(
        chat_id=message.from_user.id,
        message_id=bot_msg_id,
        text=text,
        parse_mode="HTML",
        reply_markup=SellerKeyboards.skipped_field("Screenshots")
    )
    return SELL_SCREENSHOTS

async def screenshot_input_handler(update: Update, context: CallbackContext) -> int:
    message = update.message
    photos = message.photo
    
    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    if not bot_msg_id or not photos:
        return SELL_SCREENSHOTS

    # Capture highest quality photo ID
    photo_id = photos[-1].file_id
    context.user_data["sell_screenshots"].append(photo_id)
    current_count = len(context.user_data["sell_screenshots"])

    if current_count >= 3:
        return await prompt_for_notes(message.from_user.id, bot_msg_id, context)

    # Allow more or submit done
    text = (
        f"{Visual.header('Sell Your Agent')}\n"
        f"🖼 Received {current_count}/3 screenshots.\n\n"
        f"Send another image, or click below to proceed:"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Done Uploading", callback_data="seller_flow:skip:Screenshots")],
        [InlineKeyboardButton("🚫 Cancel", callback_data="seller_flow:cancel")]
    ])
    await context.bot.edit_message_text(
        chat_id=message.from_user.id,
        message_id=bot_msg_id,
        text=text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    return SELL_SCREENSHOTS

async def skip_screenshots_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    return await prompt_for_notes(query.from_user.id, query.message.message_id, context)

async def prompt_for_notes(chat_id: int, bot_msg_id: int, context: CallbackContext) -> int:
    text = (
        f"{Visual.header('Sell Your Agent')}\n"
        f"📦 Name: <b>{context.user_data['sell_form']['name']}</b>\n\n"
        f"Step 9: 📝 Add any <b>Extra notes</b> for the administrators (or skip):"
    )
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=bot_msg_id,
        text=text,
        parse_mode="HTML",
        reply_markup=SellerKeyboards.skipped_field("Notes")
    )
    return SELL_NOTES

async def notes_input_handler(update: Update, context: CallbackContext) -> int:
    message = update.message
    notes = message.text.strip()
    
    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    if not bot_msg_id:
        return ConversationHandler.END

    context.user_data["sell_form"]["extra_notes"] = notes
    return await save_agent_submission(message.from_user.id, bot_msg_id, context)

async def skip_notes_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    context.user_data["sell_form"]["extra_notes"] = None
    await query.answer()
    return await save_agent_submission(query.from_user.id, query.message.message_id, context)

async def save_agent_submission(seller_id: int, bot_msg_id: int, context: CallbackContext) -> int:
    form = context.user_data["sell_form"]
    screenshots = context.user_data["sell_screenshots"]

    async with AsyncSessionLocal() as session:
        market_service = MarketplaceService(session)
        
        # Save submission to DB
        agent = await market_service.submit_agent(
            seller_id=seller_id,
            category_id=form["category_id"],
            name=form["name"],
            description=form["description"],
            features=form["features"],
            price=form["price"],
            file_id=form["file_id"],
            screenshot_ids=screenshots,
            demo_url=form["demo_url"],
            extra_notes=form["extra_notes"]
        )

        text = (
            f"{Visual.header('Submission Complete!')}\n"
            f"🎉 Your agent listing <b>{form['name']}</b> has been sent for review!\n\n"
            f"Moderators have been notified. Once approved, the listing will be published in the catalog.\n"
            f"Submission ID: #{agent.id}"
        )
        await context.bot.edit_message_text(
            chat_id=seller_id,
            message_id=bot_msg_id,
            text=text,
            parse_mode="HTML",
            reply_markup=UserKeyboards.back_to_main()
        )
        
    return ConversationHandler.END

async def cancel_submission_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer("🚫 Submission cancelled.")
    
    # Return to main dashboard
    from bot.handlers.user.base import show_main_menu
    async with AsyncSessionLocal() as session:
        await show_main_menu(update, context, session, query.from_user.id, query.from_user.first_name, edit=True)
        
    return ConversationHandler.END

seller_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(sell_agent_start_callback, pattern="^user_menu:sell$")],
    states={
        SELL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_input_handler)],
        SELL_CATEGORY: [CallbackQueryHandler(category_select_callback, pattern="^seller_flow:cat:\\d+$")],
        SELL_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, description_input_handler)],
        SELL_FEATURES: [MessageHandler(filters.TEXT & ~filters.COMMAND, features_input_handler)],
        SELL_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price_input_handler)],
        SELL_DEMO: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, demo_input_handler),
            CallbackQueryHandler(skip_demo_callback, pattern="^seller_flow:skip:Demo$")
        ],
        SELL_FILE: [MessageHandler(filters.Document.ALL, file_input_handler)],
        SELL_SCREENSHOTS: [
            MessageHandler(filters.PHOTO, screenshot_input_handler),
            CallbackQueryHandler(skip_screenshots_callback, pattern="^seller_flow:skip:Screenshots$")
        ],
        SELL_NOTES: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, notes_input_handler),
            CallbackQueryHandler(skip_notes_callback, pattern="^seller_flow:skip:Notes$")
        ]
    },
    fallbacks=[CallbackQueryHandler(cancel_submission_callback, pattern="^seller_flow:cancel$")],
    per_message=False
)
