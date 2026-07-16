import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler, MessageHandler, ConversationHandler, filters
from bot.database.connection import AsyncSessionLocal
from bot.services.backup_service import BackupService
from bot.repositories.admin_repo import AdminRepository
from bot.keyboards.admin_kb import AdminKeyboards
from bot.filters.admin_filter import admin_only
from bot.middlewares.blacklist import blacklist_check
from bot.middlewares.rate_limit import rate_limit
from bot.utils.visual import Visual

logger = logging.getLogger(__name__)

# FSM state constant
RESTORE_BACKUP_STATE = 603

@rate_limit
@blacklist_check
@admin_only
async def admin_settings_menu_callback(update: Update, context: CallbackContext):
    """Lists configuration keys."""
    query = update.callback_query
    
    async with AsyncSessionLocal() as session:
        admin_repo = AdminRepository(session)
        maintenance = await admin_repo.get_setting("maintenance_mode")
        maintenance_status = "ACTIVE 🔴" if maintenance == "true" else "INACTIVE 🟢"

        text = (
            f"{Visual.header('Global Settings')}\n"
            f"Modify system parameters and toggles below:\n\n"
            f"🔧 Maintenance Mode: <b>{maintenance_status}</b>"
        )
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=AdminKeyboards.settings_menu()
        )
        await query.answer()

@rate_limit
@blacklist_check
@admin_only
async def admin_toggle_maintenance_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    admin_id = query.from_user.id

    async with AsyncSessionLocal() as session:
        admin_repo = AdminRepository(session)
        current = await admin_repo.get_setting("maintenance_mode")
        new_val = "true" if current != "true" else "false"
        await admin_repo.set_setting("maintenance_mode", new_val)
        await admin_repo.add_audit_log(admin_id, "TOGGLE_MAINTENANCE", f"Set maintenance mode to {new_val}")
        await session.commit()
        await query.answer(f"🔧 Maintenance Mode set to {new_val}")
        
    await admin_settings_menu_callback(update, context)

@rate_limit
@blacklist_check
@admin_only
async def admin_backups_menu_callback(update: Update, context: CallbackContext):
    """Renders backup options."""
    query = update.callback_query
    await query.edit_message_text(
        text=f"{Visual.header('Backups & Restore')}\nManage database snapshots and configurations:",
        parse_mode="HTML",
        reply_markup=AdminKeyboards.backups_menu()
    )
    await query.answer()

@rate_limit
@blacklist_check
@admin_only
async def admin_create_backup_callback(update: Update, context: CallbackContext):
    """Generates backup zip and delivers it to admin chat."""
    query = update.callback_query
    admin_id = query.from_user.id
    await query.answer("💾 Creating database snapshot...")

    async with AsyncSessionLocal() as session:
        backup_service = BackupService(session)
        zip_path = await backup_service.create_backup(admin_id, is_auto=False)

        if os.path.exists(zip_path):
            # Send file
            await context.bot.send_document(
                chat_id=admin_id,
                document=open(zip_path, "rb"),
                filename=os.path.basename(zip_path),
                caption="💾 <b>Database Backup Zip</b>\n\nContains full database state serialized in JSON compression.",
                parse_mode="HTML",
                reply_markup=AdminKeyboards.back_to_dash()
            )
        else:
            await query.edit_message_text(
                text="❌ Backup creation failed.",
                reply_markup=AdminKeyboards.back_to_dash()
            )

# RESTORE BACKUP FSM FLOW
@rate_limit
@blacklist_check
@admin_only
async def admin_restore_start_callback(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    text = (
        f"{Visual.header('Restore Backup')}\n"
        f"📂 Please upload the database backup ZIP file (.zip) below:"
    )
    msg = await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=AdminKeyboards.back_to_dash()
    )
    context.user_data["menu_msg_id"] = msg.message_id
    return RESTORE_BACKUP_STATE

async def backup_file_handler(update: Update, context: CallbackContext) -> int:
    message = update.message
    admin_id = message.from_user.id
    doc = message.document

    try:
        await context.bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
    except Exception:
        pass

    bot_msg_id = context.user_data.get("menu_msg_id")
    if not bot_msg_id:
        return ConversationHandler.END

    if not doc or not doc.file_name.endswith(".zip"):
        await context.bot.edit_message_text(
            chat_id=admin_id,
            message_id=bot_msg_id,
            text="⚠️ Invalid file. Please upload a valid database backup zip file:",
            reply_markup=AdminKeyboards.back_to_dash()
        )
        return RESTORE_BACKUP_STATE

    # Download document
    file_info = await context.bot.get_file(doc.file_id)
    temp_path = f"backups/temp_restore_{admin_id}.zip"
    os.makedirs("backups", exist_ok=True)
    
    await file_info.download_to_drive(temp_path)

    async with AsyncSessionLocal() as session:
        backup_service = BackupService(session)
        success = await backup_service.restore_backup(temp_path, admin_id)
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

        if success:
            text = (
                f"{Visual.header('Restore Complete')}\n"
                f"✅ Database has been successfully restored. All tables repopulated."
            )
        else:
            text = (
                f"{Visual.header('Restore Failed')}\n"
                f"❌ An error occurred while parsing the backup file or writing to the database."
            )

        await context.bot.edit_message_text(
            chat_id=admin_id,
            message_id=bot_msg_id,
            text=text,
            parse_mode="HTML",
            reply_markup=AdminKeyboards.back_to_dash()
        )

    return ConversationHandler.END

backup_restore_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(admin_restore_start_callback, pattern="^admin:backups:restore$")],
    states={
        RESTORE_BACKUP_STATE: [MessageHandler(filters.Document.ZIP, backup_file_handler)]
    },
    fallbacks=[CallbackQueryHandler(admin_backups_menu_callback, pattern="^admin:menu:backups$")],
    per_message=False
)
