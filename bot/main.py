import os
import asyncio
import logging
from aiohttp import web
from telegram.ext import ApplicationBuilder
from bot.config import settings
from bot.database.connection import init_db, AsyncSessionLocal
from bot.cache.redis_cache import cache
from bot.scheduler.jobs import setup_scheduler
from bot.handlers import register_all_handlers
from bot.utils.logger import logger

async def handle_health(request):
    """Simple HTTP handler returning health stats."""
    return web.json_response({"status": "healthy", "bot": "active"})

async def start_web_server():
    """Starts a background HTTP health check server binding to Render's PORT."""
    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)
    
    port = int(os.getenv("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"HTTP health check server listening on port {port}")

async def seed_default_settings():
    """Seeds default configurations in the database if empty."""
    from bot.repositories.admin_repo import AdminRepository
    async with AsyncSessionLocal() as session:
        admin_repo = AdminRepository(session)
        defaults = {
            "referral_reward": "2.0",
            "daily_reward": "1.0",
            "welcome_reward": "1.0",
            "commission_rate": "0.05",
            "maintenance_mode": "false"
        }
        for key, val in defaults.items():
            current = await admin_repo.get_setting(key)
            if current is None:
                await admin_repo.set_setting(key, val)
        await session.commit()
        logger.info("Default system settings seeded successfully.")

async def main():
    logger.info("Starting Money Agent Marketplace Bot initialization...")

    # 1. Initialize DB tables
    try:
        await init_db()
        logger.info("Database connection and tables initialized.")
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}")
        return

    # 2. Seed settings
    await seed_default_settings()

    # 3. Connect to Cache (Redis or fallback)
    await cache.connect()

    # 4. Initialize Scheduler background jobs
    setup_scheduler()

    # Start HTTP health check server for Render Web Service
    await start_web_server()

    # 5. Build telegram application
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN is not set in environment! Exiting.")
        return

    application = ApplicationBuilder().token(settings.BOT_TOKEN).build()

    # Register global error handler
    from telegram import Update
    from telegram.ext import CallbackContext

    async def error_handler(update: object, context: CallbackContext) -> None:
        logger.error(f"Exception while handling an update: {context.error}")
        if isinstance(update, Update) and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⚠️ <b>An unexpected error occurred.</b> Please try again or run /start to reset.",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    application.add_error_handler(error_handler)

    # 6. Register all handlers (User, Seller, Support, Admin)
    register_all_handlers(application)
    logger.info("Handlers registered successfully.")

    # 7. Start polling
    logger.info("Bot is active and listening for updates...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    # Keep running until terminated
    # This block allows running inside standard asyncio loop (Render-friendly)
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
        logger.info("Termination signal received. Shutting down...")
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        logger.info("Bot shut down successfully.")

if __name__ == "__main__":
    # Configure root level logging redirect to Loguru
    logging.basicConfig(handlers=[logging.NullHandler()], level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
