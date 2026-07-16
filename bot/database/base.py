from bot.models.base import Base

# Import all models here so Alembic can discover their metadata
from bot.models.user import User, Referral, DailyReward, Blacklist, Ban
from bot.models.agent import Category, Agent, Order, OrderItem, Favorite, Wishlist
from bot.models.ticket import Ticket, TicketMessage, Report
from bot.models.settings import Setting, ForceJoinChannel, Coupon, CouponUsage
from bot.models.logs import Broadcast, AuditLog, Notification, BackupRecord
