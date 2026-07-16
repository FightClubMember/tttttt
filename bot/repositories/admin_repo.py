from typing import List, Optional
from sqlalchemy import select, func, desc, update
from sqlalchemy.orm import selectinload
from bot.repositories.base import BaseRepository
from bot.models.settings import Setting, ForceJoinChannel, Coupon, CouponUsage
from bot.models.ticket import Ticket, TicketMessage, Report
from bot.models.logs import Broadcast, AuditLog, Notification, BackupRecord

class AdminRepository(BaseRepository):
    # Setting operations
    async def get_setting(self, key: str) -> Optional[str]:
        stmt = select(Setting).where(Setting.key == key)
        res = await self.execute(stmt)
        setting = res.scalar_one_or_none()
        return setting.value if setting else None

    async def set_setting(self, key: str, value: str):
        stmt = select(Setting).where(Setting.key == key)
        res = await self.execute(stmt)
        setting = res.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            await self.add(Setting(key=key, value=value))

    # Force Join
    async def get_all_force_join_channels(self, include_inactive: bool = False) -> List[ForceJoinChannel]:
        stmt = select(ForceJoinChannel)
        if not include_inactive:
            stmt = stmt.where(ForceJoinChannel.is_active == True)
        stmt = stmt.order_by(ForceJoinChannel.order.asc())
        res = await self.execute(stmt)
        return list(res.scalars().all())

    async def get_force_join_channel(self, channel_id: int) -> Optional[ForceJoinChannel]:
        stmt = select(ForceJoinChannel).where(ForceJoinChannel.id == channel_id)
        res = await self.execute(stmt)
        return res.scalar_one_or_none()

    # Coupons
    async def get_coupon(self, code: str) -> Optional[Coupon]:
        stmt = select(Coupon).where(Coupon.code == code)
        res = await self.execute(stmt)
        return res.scalar_one_or_none()

    async def get_all_coupons(self) -> List[Coupon]:
        stmt = select(Coupon).order_by(desc(Coupon.id))
        res = await self.execute(stmt)
        return list(res.scalars().all())

    async def get_coupon_usage(self, user_id: int, coupon_id: int) -> Optional[CouponUsage]:
        stmt = select(CouponUsage).where(CouponUsage.user_id == user_id, CouponUsage.coupon_id == coupon_id)
        res = await self.execute(stmt)
        return res.scalar_one_or_none()

    # Support tickets
    async def get_ticket(self, ticket_id: int) -> Optional[Ticket]:
        stmt = select(Ticket).where(Ticket.id == ticket_id).options(selectinload(Ticket.messages))
        res = await self.execute(stmt)
        return res.scalar_one_or_none()

    async def get_user_tickets(self, user_id: int) -> List[Ticket]:
        stmt = select(Ticket).where(Ticket.user_id == user_id).order_by(desc(Ticket.created_at))
        res = await self.execute(stmt)
        return list(res.scalars().all())

    async def get_all_tickets(self, status: Optional[str] = None) -> List[Ticket]:
        stmt = select(Ticket)
        if status:
            stmt = stmt.where(Ticket.status == status)
        stmt = stmt.order_by(desc(Ticket.created_at))
        res = await self.execute(stmt)
        return list(res.scalars().all())

    # Notifications
    async def get_unread_notifications(self, user_id: int) -> List[Notification]:
        stmt = select(Notification).where(Notification.user_id == user_id, Notification.is_read == False).order_by(desc(Notification.created_at))
        res = await self.execute(stmt)
        return list(res.scalars().all())

    async def get_all_notifications(self, user_id: int) -> List[Notification]:
        stmt = select(Notification).where(Notification.user_id == user_id).order_by(desc(Notification.created_at))
        res = await self.execute(stmt)
        return list(res.scalars().all())

    async def mark_notifications_read(self, user_id: int):
        stmt = update(Notification).where(Notification.user_id == user_id, Notification.is_read == False).values(is_read=True)
        await self.execute(stmt)

    async def add_notification(self, user_id: int, text: str):
        notif = Notification(user_id=user_id, text=text)
        await self.add(notif)

    # Auditing
    async def add_audit_log(self, user_id: int, action: str, details: str):
        log = AuditLog(user_id=user_id, action=action, details=details)
        await self.add(log)

    async def get_audit_logs(self, limit: int = 100) -> List[AuditLog]:
        stmt = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
        res = await self.execute(stmt)
        return list(res.scalars().all())
