import io
import logging
from telegram import Update, InputFile
from telegram.ext import CallbackContext, CallbackQueryHandler, MessageHandler, ConversationHandler, filters
from bot.database.connection import AsyncSessionLocal
from bot.services.user_service import UserService
from bot.repositories.user_repo import UserRepository
from bot.repositories.admin_repo import AdminRepository
from bot.keyboards.user_kb import UserKeyboards
from bot.middlewares.blacklist import blacklist_check
from bot.middlewares.rate_limit import rate_limit
from bot.utils.visual import Visual
from bot.utils.formatter import Formatter

logger = logging.getLogger(__name__)

# FSM state constant
COUPON_INPUT_STATE = 600

@rate_limit
@blacklist_check
async def wallet_menu_callback(update: Update, context: CallbackContext):
    """Renders user's wallet and transaction stats."""
    query = update.callback_query
    user_id = query.from_user.id

    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_user(user_id)
        if not user:
            await query.answer("User not found.", show_alert=True)
            return

        text = (
            f"{Visual.header('Your Wallet')}\n"
            f"💰 Credits Balance: <b>{user.credits} Credits</b>\n"
            f"📈 Lifetime Earned: <b>{user.lifetime_earned} Credits</b>\n"
            f"📉 Lifetime Spent: <b>{user.lifetime_spent} Credits</b>\n\n"
            f"🛒 Purchased Credits: <b>{user.purchased_credits} Credits</b>\n"
            f"📤 Sold Credits: <b>{user.sold_credits} Credits</b>\n"
            f"{Visual.footer()}"
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=UserKeyboards.wallet_menu()
        )
        await query.answer()

@rate_limit
@blacklist_check
async def referral_menu_callback(update: Update, context: CallbackContext):
    """Renders referral rewards statistics and unique invitation link."""
    query = update.callback_query
    user_id = query.from_user.id
    bot_info = await context.bot.get_me()

    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        admin_repo = AdminRepository(session)
        
        # Load referral settings rewards
        ref_reward_str = await admin_repo.get_setting("referral_reward")
        ref_reward = float(ref_reward_str) if ref_reward_str else 2.0
        
        ref_count = await user_repo.get_referral_count(user_id)
        leaderboard = await user_repo.get_referral_leaderboard(limit=5)
        
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"

        text = (
            f"{Visual.header('Referral Program')}\n"
            f"👥 Invite your friends and earn premium rewards!\n\n"
            f"💎 Reward: <b>+{ref_reward} Credits</b> per verified referral.\n"
            f"📊 Total Referrals: <b>{ref_count} Users</b>\n\n"
            f"🔗 Your Invite Link:\n<code>{ref_link}</code>\n\n"
            f"🏆 <b>Referral Leaderboard</b>\n"
        )
        
        for idx, (usr, count) in enumerate(leaderboard, 1):
            name = usr.first_name or f"User {usr.id}"
            text += f" {idx}. {name} — <b>{count} invites</b>\n"

        text += Visual.footer()
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=UserKeyboards.back_to_main()
        )
        await query.answer()

@rate_limit
@blacklist_check
async def export_statement_callback(update: Update, context: CallbackContext):
    """Generates and uploads transaction history statement in CSV format."""
    query = update.callback_query
    user_id = query.from_user.id

    await query.answer("⏳ Compiling account statement...")

    async with AsyncSessionLocal() as session:
        agent_repo = AgentRepository(session)
        user_orders = await agent_repo.get_user_orders(user_id)
        user_sales = await agent_repo.get_user_sales(user_id)

        csv_content = Formatter.generate_statement_csv(user_id, user_orders, user_sales)
        
        # Create bytes buffer
        buffer = io.BytesIO(csv_content.encode("utf-8"))
        buffer.name = f"statement_{user_id}.csv"

        # Send statement file to user chat
        await context.bot.send_document(
            chat_id=user_id,
            document=buffer,
            filename=f"wallet_statement.csv",
            caption="📄 Your account transaction statement (CSV). Check purchases & sales history.",
            reply_markup=UserKeyboards.back_to_main()
        )

# COUPONS FSM Conversation flow
@rate_limit
@blacklist_check
async def coupon_start_callback(update: Update, context: CallbackContext) -> int:
    """Prompts user to type coupon code (FSM Start)."""
    query = update.callback_query
    user_id = query.from_user.id
    
    text = (
        f"{Visual.header('Redeem Coupon')}\n"
        f"🎟 Enter your promotional coupon code below.\n\n"
        f"💡 Codes are case-insensitive."
    )
    msg = await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=UserKeyboards.back_to_main()
    )
    
    # Store bot message ID to edit later
    context.user_data["menu_msg_id"] = msg.message_id
    return COUPON_INPUT_STATE

async def coupon_input_handler(update: Update, context: CallbackContext) -> int:
    """Processes typed coupon text, deletes user input, and edits bot prompt menu."""
    message = update.message
    user_id = message.from_user.id
    code_text = message.text.strip()
    
    # Delete user text input immediately to keep chat feed clean
    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    if not bot_msg_id:
        # Fallback if ID is lost
        await message.reply_text("Process timeout. Please go back to Main Menu.")
        return ConversationHandler.END

    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        success, feedback = await user_service.redeem_coupon(user_id, code_text)

        # Edit original bot message with success/error details
        await context.bot.edit_message_text(
            chat_id=user_id,
            message_id=bot_msg_id,
            text=f"{Visual.header('Redeem Coupon')}\n{feedback}\n{Visual.footer()}",
            parse_mode="HTML",
            reply_markup=UserKeyboards.back_to_main()
        )

    return ConversationHandler.END

async def coupon_cancel_callback(update: Update, context: CallbackContext) -> int:
    """Aborts FSM coupon flow."""
    query = update.callback_query
    await query.answer()
    return ConversationHandler.END

coupon_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(coupon_start_callback, pattern="^wallet:redeem_coupon$")],
    states={
        COUPON_INPUT_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, coupon_input_handler)]
    },
    fallbacks=[CallbackQueryHandler(coupon_cancel_callback, pattern="^user_menu:main$")],
    per_message=False
)
