import datetime
import json
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from bot.repositories.user_repo import UserRepository
from bot.repositories.admin_repo import AdminRepository
from bot.models.user import User, DailyReward, Referral
from bot.models.settings import Coupon, CouponUsage

class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.admin_repo = AdminRepository(session)

    async def get_or_create_user(self, user_id: int, username: str, first_name: str, referrer_id: Optional[int] = None) -> Tuple[User, bool]:
        """Gets existing user or registers a new user. Returns user object and is_new boolean."""
        user = await self.user_repo.get_user(user_id)
        if user:
            # Update username/first_name if changed
            user.username = username
            user.first_name = first_name
            await self.session.commit()
            return user, False

        # Ensure referrer exists and is not the user itself
        ref_id = None
        if referrer_id and referrer_id != user_id:
            ref_user = await self.user_repo.get_user(referrer_id)
            if ref_user:
                ref_id = referrer_id

        user = await self.user_repo.create_user(
            user_id=user_id,
            username=username,
            first_name=first_name,
            referrer_id=ref_id
        )
        
        # Save referral record as pending if referrer was attached
        if ref_id:
            referral = Referral(
                referrer_id=ref_id,
                referee_id=user_id,
                status="pending"
            )
            await self.user_repo.add(referral)

        await self.session.commit()
        return user, True

    async def process_referral_rewards(self, user_id: int) -> Tuple[bool, float, int]:
        """
        Gives referral rewards if user was referred, pending, and now finishes verification.
        Returns (success, referrer_credits_rewarded, referrer_id)
        """
        # Find pending referrals where this user is the referee
        referrals = await self.user_repo.get_referrals_by_referee(user_id)
        pending_ref = None
        for r in referrals:
            if r.status == "pending":
                pending_ref = r
                break

        if not pending_ref:
            return False, 0.0, 0

        # Retrieve rewards from DB settings
        ref_reward_str = await self.admin_repo.get_setting("referral_reward")
        ref_reward = float(ref_reward_str) if ref_reward_str else 2.0

        welcome_reward_str = await self.admin_repo.get_setting("welcome_reward")
        welcome_reward = float(welcome_reward_str) if welcome_reward_str else 1.0

        # Load referrer and referee
        referrer = await self.user_repo.get_user(pending_ref.referrer_id)
        referee = await self.user_repo.get_user(user_id)

        if referrer and referee:
            # Update referrer
            referrer.credits += ref_reward
            referrer.lifetime_earned += ref_reward
            
            # Update referee (Welcome bonus)
            referee.credits += welcome_reward
            referee.lifetime_earned += welcome_reward

            # Update referral record status
            pending_ref.status = "verified"
            pending_ref.reward_credits = ref_reward
            
            # Push notifications
            await self.admin_repo.add_notification(
                pending_ref.referrer_id, 
                f"👥 Referral Reward! Your invitee completed join verification. Received +{ref_reward} Credits."
            )
            await self.admin_repo.add_notification(
                user_id, 
                f"🎉 Welcome Reward! Received +{welcome_reward} Credits for joining the community via referral."
            )

            await self.session.commit()
            return True, ref_reward, referrer.id

        return False, 0.0, 0

    async def check_in(self, user_id: int) -> Tuple[bool, str, float]:
        """
        Executes daily check-in.
        Returns (success, message, credits_earned)
        """
        user = await self.user_repo.get_user(user_id)
        if not user:
            return False, "User not found", 0.0

        daily = await self.user_repo.get_daily_reward(user_id)
        now = datetime.datetime.utcnow()

        # Config rewards and cooldown
        reward_base_str = await self.admin_repo.get_setting("daily_reward")
        reward_base = float(reward_base_str) if reward_base_str else 1.0
        
        double_rewards_str = await self.admin_repo.get_setting("double_rewards")
        double_rewards = double_rewards_str == "true"

        if daily:
            cooldown_seconds = 86400  # 24 hours
            time_diff = (now - daily.last_check_in).total_seconds()
            if time_diff < cooldown_seconds:
                remaining = cooldown_seconds - time_diff
                hours = int(remaining // 3600)
                minutes = int((remaining % 3600) // 60)
                return False, f"🕒 Check-in is on cooldown. Try again in {hours}h {minutes}m.", 0.0

            # Check if streak is maintained (checked in within 48 hours)
            if time_diff < 172800: # 48 hours
                daily.streak += 1
            else:
                daily.streak = 1
                
            daily.last_check_in = now
        else:
            daily = DailyReward(user_id=user_id, last_check_in=now, streak=1)
            await self.user_repo.add(daily)

        # Random reward between 0.6 and 1.0 credits
        import random
        earned = round(random.uniform(0.6, 1.0), 2)
        if double_rewards:
            earned *= 2

        user.credits += earned
        user.lifetime_earned += earned
        
        await self.admin_repo.add_notification(
            user_id, 
            f"🎁 Daily Check-in! Streak: {daily.streak} days. Earned +{earned} Credits."
        )

        await self.session.commit()
        
        msg = f"🎉 <b>Daily Reward Claimed!</b>\n"
        msg += f"🔥 Current Streak: <b>{daily.streak} Days</b>\n"
        msg += f"💎 Earned: <b>+{earned} Credits</b>"
        if double_rewards:
            msg += " (2x Event Active!)\n"
            
        return True, msg, earned

    async def redeem_coupon(self, user_id: int, code: str) -> Tuple[bool, str]:
        """
        Redeems a promotional coupon code.
        Returns (success, message)
        """
        user = await self.user_repo.get_user(user_id)
        if not user:
            return False, "User not found."

        coupon = await self.admin_repo.get_coupon(code.upper())
        if not coupon or not coupon.active:
            return False, "❌ Invalid or inactive coupon code."

        now = datetime.datetime.utcnow()
        if coupon.expiry_date and now > coupon.expiry_date:
            return False, "❌ Coupon has expired."

        if coupon.current_uses >= coupon.max_uses:
            return False, "❌ Coupon maximum usage reached."

        if user.credits < coupon.min_credits:
            return False, f"❌ You need at least {coupon.min_credits} credits to redeem this coupon."

        # Check if already used by this user (one-time check)
        if coupon.is_one_time:
            existing = await self.admin_repo.get_coupon_usage(user_id, coupon.id)
            if existing:
                return False, "❌ You have already redeemed this coupon."

        # Record usage
        usage = CouponUsage(user_id=user_id, coupon_id=coupon.id)
        await self.admin_repo.add(usage)

        # Update coupon stats
        coupon.current_uses += 1

        # Reward credits
        user.credits += coupon.reward_credits
        user.lifetime_earned += coupon.reward_credits

        # Notification
        await self.admin_repo.add_notification(
            user_id, 
            f"🎟 Coupon Redeemed! Code: {code.upper()}. Received +{coupon.reward_credits} Credits."
        )

        await self.session.commit()
        return True, f"✅ <b>Coupon Redeemed!</b>\n💎 Received: <b>+{coupon.reward_credits} Credits</b>"
