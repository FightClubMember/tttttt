import datetime
from sqlalchemy import BigInteger, String, Float, Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from bot.models.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=True)
    credits: Mapped[float] = mapped_column(Float, default=0.0)
    referrer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    joined_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    role: Mapped[str] = mapped_column(String(20), default="user") # 'user', 'seller', 'admin'
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False)
    warnings_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Financial/credit accounting
    lifetime_earned: Mapped[float] = mapped_column(Float, default=0.0)
    lifetime_spent: Mapped[float] = mapped_column(Float, default=0.0)
    purchased_credits: Mapped[float] = mapped_column(Float, default=0.0)
    sold_credits: Mapped[float] = mapped_column(Float, default=0.0)

    # Relationships
    daily_reward = relationship("DailyReward", back_populates="user", uselist=False, cascade="all, delete-orphan")
    blacklist_entry = relationship("Blacklist", back_populates="user", uselist=False, cascade="all, delete-orphan")
    ban_entry = relationship("Ban", back_populates="user", uselist=False, cascade="all, delete-orphan")

class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    referee_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending") # 'pending', 'verified'
    reward_credits: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

class DailyReward(Base):
    __tablename__ = "daily_rewards"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    last_check_in: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    streak: Mapped[int] = mapped_column(Integer, default=0)

    user = relationship("User", back_populates="daily_reward")

class Blacklist(Base):
    __tablename__ = "blacklist"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    blacklisted_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="blacklist_entry")

class Ban(Base):
    __tablename__ = "bans"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    banned_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    banned_by: Mapped[int] = mapped_column(BigInteger, nullable=True)

    user = relationship("User", back_populates="ban_entry")
