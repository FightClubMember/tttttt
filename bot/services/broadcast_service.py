import asyncio
import datetime
import logging
from typing import List, Set
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot
from telegram.error import Forbidden, TelegramError, RetryAfter
from bot.repositories.user_repo import UserRepository
from bot.repositories.admin_repo import AdminRepository
from bot.models.logs import Broadcast

logger = logging.getLogger(__name__)

# Global dictionary to track active broadcasts that can be cancelled
active_broadcast_tasks = {}

class BroadcastService:
    def __init__(self, session: AsyncSession, bot: Bot):
        self.session = session
        self.bot = bot
        self.user_repo = UserRepository(session)
        self.admin_repo = AdminRepository(session)

    async def start_broadcast(
        self,
        broadcast_id: int,
        from_chat_id: int,
        message_id: int,
        target_group: str = "all"
    ):
        """Starts the broadcast loop as a task."""
        task = asyncio.create_task(
            self._run_broadcast_loop(broadcast_id, from_chat_id, message_id, target_group)
        )
        active_broadcast_tasks[broadcast_id] = task
        return task

    async def cancel_broadcast(self, broadcast_id: int) -> bool:
        """Cancels a currently running broadcast."""
        task = active_broadcast_tasks.get(broadcast_id)
        if task:
            task.cancel()
            active_broadcast_tasks.pop(broadcast_id, None)
            return True
        return False

    async def _run_broadcast_loop(
        self,
        broadcast_id: int,
        from_chat_id: int,
        message_id: int,
        target_group: str
    ):
        try:
            # Query broadcast record
            stmt = (
                self.session.query(Broadcast)
                if hasattr(self.session, "query")
                else None
            )
            # Fetch record
            from sqlalchemy import select
            stmt = select(Broadcast).where(Broadcast.id == broadcast_id)
            res = await self.session.execute(stmt)
            broadcast = res.scalar_one_or_none()
            if not broadcast:
                return

            broadcast.status = "running"
            await self.session.commit()

            # Filter targets
            users = await self.user_repo.get_all_users()
            targets = []
            for u in users:
                if target_group == "all":
                    targets.append(u.id)
                elif target_group == "admins" and u.role == "admin":
                    targets.append(u.id)
                elif target_group == "sellers" and u.role in ["seller", "admin"]:
                    targets.append(u.id)
                elif target_group == "buyers":
                    # Simple heuristic: users who spent credits are buyers
                    if u.lifetime_spent > 0:
                        targets.append(u.id)

            broadcast.total_users = len(targets)
            await self.session.commit()

            delivered = 0
            failed = 0
            blocked = 0

            # Execute broadcast
            for idx, target_id in enumerate(targets):
                try:
                    # Telegram API copy_message duplicates text, photos, files, polls, buttons, etc.
                    await self.bot.copy_message(
                        chat_id=target_id,
                        from_chat_id=from_chat_id,
                        message_id=message_id
                    )
                    delivered += 1
                except Forbidden:
                    blocked += 1
                except RetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                    # Retry once
                    try:
                        await self.bot.copy_message(
                            chat_id=target_id,
                            from_chat_id=from_chat_id,
                            message_id=message_id
                        )
                        delivered += 1
                    except Forbidden:
                        blocked += 1
                    except Exception:
                        failed += 1
                except TelegramError:
                    failed += 1
                except Exception:
                    failed += 1

                # Update database stats periodically (e.g. every 10 users)
                if idx % 10 == 0 or idx == len(targets) - 1:
                    # Re-fetch broadcast within session context
                    res = await self.session.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
                    b_rec = res.scalar_one_or_none()
                    if b_rec:
                        b_rec.delivered = delivered
                        b_rec.failed = failed
                        b_rec.blocked = blocked
                        await self.session.commit()

                # Sleep 35ms to respect API rate limits (max 30 msgs/sec -> ~33ms delay)
                await asyncio.sleep(0.035)

            # Mark complete
            res = await self.session.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
            b_rec = res.scalar_one_or_none()
            if b_rec:
                b_rec.status = "completed"
                b_rec.finished_at = datetime.datetime.utcnow()
                await self.session.commit()

        except asyncio.CancelledError:
            # Re-fetch and mark cancelled
            res = await self.session.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
            b_rec = res.scalar_one_or_none()
            if b_rec:
                b_rec.status = "cancelled"
                b_rec.finished_at = datetime.datetime.utcnow()
                await self.session.commit()
            logger.info(f"Broadcast {broadcast_id} was cancelled by admin.")
            
        except Exception as e:
            logger.error(f"Error executing broadcast {broadcast_id}: {e}")
            res = await self.session.execute(select(Broadcast).where(Broadcast.id == broadcast_id))
            b_rec = res.scalar_one_or_none()
            if b_rec:
                b_rec.status = "failed"
                b_rec.finished_at = datetime.datetime.utcnow()
                await self.session.commit()
        finally:
            active_broadcast_tasks.pop(broadcast_id, None)
