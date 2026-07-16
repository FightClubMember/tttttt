import os
import json
import zipfile
import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models import Base, User, Category, Agent, Order, OrderItem, Setting, ForceJoinChannel, Coupon, CouponUsage, DailyReward, Ticket, TicketMessage, Broadcast, BackupRecord, AuditLog
from bot.repositories.admin_repo import AdminRepository

BACKUP_DIR = "backups"

class BackupService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.admin_repo = AdminRepository(session)

    async def create_backup(self, admin_id: int, is_auto: bool = False) -> str:
        """Exports database records to a JSON file and zips it. Returns absolute zip path."""
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # Serialize model mappings
        data = {
            "users": [],
            "daily_rewards": [],
            "categories": [],
            "agents": [],
            "orders": [],
            "order_items": [],
            "settings": [],
            "force_join_channels": [],
            "coupons": [],
            "coupon_usages": [],
            "tickets": [],
            "ticket_messages": [],
            "broadcasts": [],
            "audit_logs": []
        }

        # Helper to query all records of a model
        async def fetch_all(model):
            stmt = select(model)
            res = await self.session.execute(stmt)
            return res.scalars().all()

        # Users
        for u in await fetch_all(User):
            data["users"].append({
                "id": u.id, "username": u.username, "first_name": u.first_name, "credits": u.credits,
                "referrer_id": u.referrer_id, "joined_at": u.joined_at.isoformat(), "role": u.role,
                "is_banned": u.is_banned, "is_blacklisted": u.is_blacklisted, "warnings_count": u.warnings_count,
                "lifetime_earned": u.lifetime_earned, "lifetime_spent": u.lifetime_spent,
                "purchased_credits": u.purchased_credits, "sold_credits": u.sold_credits
            })

        # Daily rewards
        for dr in await fetch_all(DailyReward):
            data["daily_rewards"].append({
                "user_id": dr.user_id, "last_check_in": dr.last_check_in.isoformat(), "streak": dr.streak
            })

        # Categories
        for c in await fetch_all(Category):
            data["categories"].append({
                "id": c.id, "name": c.name, "icon": c.icon, "banner_url": c.banner_url,
                "is_hidden": c.is_hidden, "order": c.order
            })

        # Agents
        for a in await fetch_all(Agent):
            data["agents"].append({
                "id": a.id, "category_id": a.category_id, "seller_id": a.seller_id, "name": a.name,
                "description": a.description, "features": a.features, "price": a.price, "extra_notes": a.extra_notes,
                "file_id": a.file_id, "screenshot_ids": a.screenshot_ids, "demo_url": a.demo_url,
                "version": a.version, "stock": a.stock, "downloads": a.downloads, "status": a.status,
                "release_notes": a.release_notes, "rating": a.rating, "is_featured": a.is_featured,
                "is_trending": a.is_trending, "is_pinned": a.is_pinned, "created_at": a.created_at.isoformat()
            })

        # Orders
        for o in await fetch_all(Order):
            data["orders"].append({
                "id": o.id, "buyer_id": o.buyer_id, "total_credits": o.total_credits,
                "purchased_at": o.purchased_at.isoformat(), "status": o.status
            })

        # Order Items
        for oi in await fetch_all(OrderItem):
            data["order_items"].append({
                "id": oi.id, "order_id": oi.order_id, "agent_id": oi.agent_id, "price": oi.price,
                "rating": oi.rating, "review_text": oi.review_text,
                "rated_at": oi.rated_at.isoformat() if oi.rated_at else None
            })

        # Settings
        for s in await fetch_all(Setting):
            data["settings"].append({"key": s.key, "value": s.value})

        # Force Join
        for fj in await fetch_all(ForceJoinChannel):
            data["force_join_channels"].append({
                "id": fj.id, "channel_id": fj.channel_id, "channel_username": fj.channel_username,
                "invite_link": fj.invite_link, "is_active": fj.is_active, "order": fj.order
            })

        # Coupons
        for cp in await fetch_all(Coupon):
            data["coupons"].append({
                "id": cp.id, "code": cp.code, "reward_credits": cp.reward_credits, "max_uses": cp.max_uses,
                "current_uses": cp.current_uses, "min_credits": cp.min_credits, "is_one_time": cp.is_one_time,
                "expiry_date": cp.expiry_date.isoformat() if cp.expiry_date else None, "active": cp.active
            })

        # Coupon Usages
        for cu in await fetch_all(CouponUsage):
            data["coupon_usages"].append({
                "id": cu.id, "user_id": cu.user_id, "coupon_id": cu.coupon_id, "redeemed_at": cu.redeemed_at.isoformat()
            })

        # Tickets
        for t in await fetch_all(Ticket):
            data["tickets"].append({
                "id": t.id, "user_id": t.user_id, "subject": t.subject, "status": t.status,
                "priority": t.priority, "assigned_to": t.assigned_to, "created_at": t.created_at.isoformat()
            })

        # Ticket Messages
        for tm in await fetch_all(TicketMessage):
            data["ticket_messages"].append({
                "id": tm.id, "ticket_id": tm.ticket_id, "sender_id": tm.sender_id,
                "message_text": tm.message_text, "created_at": tm.created_at.isoformat()
            })

        # Broadcasts
        for b in await fetch_all(Broadcast):
            data["broadcasts"].append({
                "id": b.id, "admin_id": b.admin_id, "total_users": b.total_users, "delivered": b.delivered,
                "failed": b.failed, "blocked": b.blocked, "status": b.status, "started_at": b.started_at.isoformat(),
                "finished_at": b.finished_at.isoformat() if b.finished_at else None
            })

        # Audit Logs
        for al in await fetch_all(AuditLog):
            data["audit_logs"].append({
                "id": al.id, "user_id": al.user_id, "action": al.action, "details": al.details,
                "created_at": al.created_at.isoformat()
            })

        # Write to JSON
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        json_filename = f"db_export_{timestamp}.json"
        zip_filename = f"backup_{timestamp}.zip"
        
        json_path = os.path.join(BACKUP_DIR, json_filename)
        zip_path = os.path.join(BACKUP_DIR, zip_filename)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Compress to ZIP
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_f:
            zip_f.write(json_path, json_filename)

        # Remove raw JSON
        os.remove(json_path)

        # Add record to DB
        file_size = os.path.getsize(zip_path)
        record = BackupRecord(
            filename=zip_filename,
            file_size=file_size,
            is_auto=is_auto
        )
        await self.admin_repo.add(record)
        await self.admin_repo.add_audit_log(admin_id, "CREATE_BACKUP", f"Database backup zip created: {zip_filename} ({file_size} bytes)")
        
        await self.session.commit()
        return zip_path

    async def restore_backup(self, zip_path: str, admin_id: int) -> bool:
        """Extracts and restores the JSON database state from a backup ZIP."""
        try:
            if not os.path.exists(zip_path):
                return False

            # Extract JSON from zip
            with zipfile.ZipFile(zip_path, "r") as zip_f:
                json_filename = [name for name in zip_f.namelist() if name.endswith(".json")][0]
                json_data_str = zip_f.read(json_filename).decode("utf-8")
                data = json.loads(json_data_str)

            # Drop and recreate all tables
            from bot.database.connection import engine
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)

            # Populate tables (Dependencies: Users -> DailyRewards / Referrals)
            # Users
            for u in data["users"]:
                user = User(
                    id=u["id"], username=u["username"], first_name=u["first_name"], credits=u["credits"],
                    referrer_id=u["referrer_id"], joined_at=datetime.datetime.fromisoformat(u["joined_at"]),
                    role=u["role"], is_banned=u["is_banned"], is_blacklisted=u["is_blacklisted"],
                    warnings_count=u["warnings_count"], lifetime_earned=u["lifetime_earned"],
                    lifetime_spent=u["lifetime_spent"], purchased_credits=u["purchased_credits"],
                    sold_credits=u["sold_credits"]
                )
                self.session.add(user)

            # Daily Rewards
            for dr in data["daily_rewards"]:
                reward = DailyReward(
                    user_id=dr["user_id"], last_check_in=datetime.datetime.fromisoformat(dr["last_check_in"]),
                    streak=dr["streak"]
                )
                self.session.add(reward)

            # Categories
            for c in data["categories"]:
                cat = Category(
                    id=c["id"], name=c["name"], icon=c["icon"], banner_url=c["banner_url"],
                    is_hidden=c["is_hidden"], order=c["order"]
                )
                self.session.add(cat)

            # Flush categories to enable agent foreign keys mapping
            await self.session.flush()

            # Agents
            for a in data["agents"]:
                agent = Agent(
                    id=a["id"], category_id=a["category_id"], seller_id=a["seller_id"], name=a["name"],
                    description=a["description"], features=a["features"], price=a["price"],
                    extra_notes=a["extra_notes"], file_id=a["file_id"], screenshot_ids=a["screenshot_ids"],
                    demo_url=a["demo_url"], version=a["version"], stock=a["stock"], downloads=a["downloads"],
                    status=a["status"], release_notes=a["release_notes"], rating=a["rating"],
                    is_featured=a["is_featured"], is_trending=a["is_trending"], is_pinned=a["is_pinned"],
                    created_at=datetime.datetime.fromisoformat(a["created_at"])
                )
                self.session.add(agent)

            # Orders
            for o in data["orders"]:
                order = Order(
                    id=o["id"], buyer_id=o["buyer_id"], total_credits=o["total_credits"],
                    purchased_at=datetime.datetime.fromisoformat(o["purchased_at"]), status=o["status"]
                )
                self.session.add(order)

            await self.session.flush()

            # Order Items
            for oi in data["order_items"]:
                item = OrderItem(
                    id=oi["id"], order_id=oi["order_id"], agent_id=oi["agent_id"], price=oi["price"],
                    rating=oi["rating"], review_text=oi["review_text"],
                    rated_at=datetime.datetime.fromisoformat(oi["rated_at"]) if oi["rated_at"] else None
                )
                self.session.add(item)

            # Settings
            for s in data["settings"]:
                self.session.add(Setting(key=s["key"], value=s["value"]))

            # Force Join
            for fj in data["force_join_channels"]:
                channel = ForceJoinChannel(
                    id=fj["id"], channel_id=fj["channel_id"], channel_username=fj["channel_username"],
                    invite_link=fj["invite_link"], is_active=fj["is_active"], order=fj["order"]
                )
                self.session.add(channel)

            # Coupons
            for cp in data["coupons"]:
                coupon = Coupon(
                    id=cp["id"], code=cp["code"], reward_credits=cp["reward_credits"], max_uses=cp["max_uses"],
                    current_uses=cp["current_uses"], min_credits=cp["min_credits"], is_one_time=cp["is_one_time"],
                    expiry_date=datetime.datetime.fromisoformat(cp["expiry_date"]) if cp["expiry_date"] else None,
                    active=cp["active"]
                )
                self.session.add(coupon)

            # Coupon Usages
            for cu in data["coupon_usages"]:
                usage = CouponUsage(
                    id=cu["id"], user_id=cu["user_id"], coupon_id=cu["coupon_id"],
                    redeemed_at=datetime.datetime.fromisoformat(cu["redeemed_at"])
                )
                self.session.add(usage)

            # Tickets
            for t in data["tickets"]:
                ticket = Ticket(
                    id=t["id"], user_id=t["user_id"], subject=t["subject"], status=t["status"],
                    priority=t["priority"], assigned_to=t["assigned_to"],
                    created_at=datetime.datetime.fromisoformat(t["created_at"])
                )
                self.session.add(ticket)

            await self.session.flush()

            # Ticket Messages
            for tm in data["ticket_messages"]:
                msg = TicketMessage(
                    id=tm["id"], ticket_id=tm["ticket_id"], sender_id=tm["sender_id"],
                    message_text=tm["message_text"], created_at=datetime.datetime.fromisoformat(tm["created_at"])
                )
                self.session.add(msg)

            # Broadcasts
            for b in data["broadcasts"]:
                broad = Broadcast(
                    id=b["id"], admin_id=b["admin_id"], total_users=b["total_users"], delivered=b["delivered"],
                    failed=b["failed"], blocked=b["blocked"], status=b["status"],
                    started_at=datetime.datetime.fromisoformat(b["started_at"]),
                    finished_at=datetime.datetime.fromisoformat(b["finished_at"]) if b["finished_at"] else None
                )
                self.session.add(broad)

            # Audit Logs
            for al in data["audit_logs"]:
                audit = AuditLog(
                    id=al["id"], user_id=al["user_id"], action=al["action"], details=al["details"],
                    created_at=datetime.datetime.fromisoformat(al["created_at"])
                )
                self.session.add(audit)

            # Write restore action in audits
            restore_audit = AuditLog(
                user_id=admin_id,
                action="RESTORE_BACKUP",
                details=f"Database state successfully restored from: {os.path.basename(zip_path)}"
            )
            self.session.add(restore_audit)

            await self.session.commit()
            return True

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to restore database backup: {e}")
            await self.session.rollback()
            return False
