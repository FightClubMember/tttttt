import datetime
import logging
from sqlalchemy import update, select
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bot.database.connection import AsyncSessionLocal
from bot.models.user import DailyReward
from bot.services.backup_service import BackupService

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

async def reset_expired_check_in_streaks():
    """Resets daily check-in streaks to 0 for users inactive for > 48 hours."""
    logger.info("Running job: reset_expired_check_in_streaks...")
    async with AsyncSessionLocal() as session:
        try:
            limit = datetime.datetime.utcnow() - datetime.timedelta(hours=48)
            stmt = (
                update(DailyReward)
                .where(DailyReward.last_check_in < limit)
                .where(DailyReward.streak > 0)
                .values(streak=0)
            )
            res = await session.execute(stmt)
            await session.commit()
            logger.info(f"Check-in streaks reset complete. Rows affected: {res.rowcount}")
        except Exception as e:
            logger.error(f"Error resetting check-in streaks: {e}")
            await session.rollback()

async def auto_daily_backup():
    """Triggers an automated daily database JSON ZIP backup."""
    logger.info("Running job: auto_daily_backup...")
    async with AsyncSessionLocal() as session:
        try:
            backup_service = BackupService(session)
            # Use user_id = 0 to denote automated system backups
            zip_path = await backup_service.create_backup(admin_id=0, is_auto=True)
            logger.info(f"Automated daily backup successful: {zip_path}")
        except Exception as e:
            logger.error(f"Error during automated daily backup: {e}")

def setup_scheduler():
    """Schedules cron background jobs."""
    # Run streak reset check every hour
    scheduler.add_job(
        reset_expired_check_in_streaks,
        "cron",
        hour="*",
        minute=0,
        id="streak_reset_job",
        replace_existing=True
    )
    
    # Run auto-backup daily at 3:00 AM UTC
    scheduler.add_job(
        auto_daily_backup,
        "cron",
        hour=3,
        minute=0,
        id="auto_backup_job",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("APScheduler background jobs initialized successfully.")
