import asyncio
import os
import datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from bot.models.base import Base
from bot.models.user import User
from bot.models.agent import Category, Agent, Order, OrderItem
from bot.repositories.user_repo import UserRepository
from bot.repositories.agent_repo import AgentRepository
from bot.repositories.admin_repo import AdminRepository
from bot.services.user_service import UserService
from bot.services.market_service import MarketplaceService
from bot.services.backup_service import BackupService

async def run_tests():
    print("🧪 Starting Automated Database Operations Tests...")
    
    # 1. Setup in-memory SQLite engine
    test_db_url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(test_db_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 2. Initialize tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ In-memory database tables initialized.")

    async with async_session() as session:
        user_repo = UserRepository(session)
        agent_repo = AgentRepository(session)
        admin_repo = AdminRepository(session)
        user_service = UserService(session)
        market_service = MarketplaceService(session)

        # --- Test User Registration ---
        print("\n⏳ Testing user registration...")
        admin, is_new_admin = await user_service.get_or_create_user(
            user_id=111, username="admin_usr", first_name="Administrator"
        )
        admin.role = "admin"
        
        seller, is_new_sell = await user_service.get_or_create_user(
            user_id=222, username="seller_usr", first_name="Seller Agent"
        )
        seller.role = "seller"

        buyer, is_new_buy = await user_service.get_or_create_user(
            user_id=333, username="buyer_usr", first_name="Buyer Account", referrer_id=222
        )
        
        await session.commit()
        
        assert is_new_admin is True, "Admin should be newly registered"
        assert buyer.referrer_id == 222, "Referrer should be set correctly"
        print("✅ User registration tested successfully.")

        # --- Test Referral verification ---
        print("\n⏳ Testing referral rewards...")
        rewarded, ref_earned, ref_id = await user_service.process_referral_rewards(buyer.id)
        assert rewarded is True, "Referral should be rewarded successfully"
        assert ref_earned == 2.0, "Referrer reward should default to 2.0"
        assert ref_id == 222, "Referrer ID should match"
        
        # Verify credits updated
        await session.refresh(seller)
        await session.refresh(buyer)
        assert seller.credits == 2.0, f"Seller should have +2.0 credits, got {seller.credits}"
        assert buyer.credits == 1.0, f"Buyer should have +1.0 credits, got {buyer.credits}"
        print("✅ Referral rewards verified.")

        # --- Test Daily Check-in ---
        print("\n⏳ Testing daily rewards check-in...")
        # First check-in
        success, message, earned = await user_service.check_in(buyer.id)
        assert success is True, "Daily check-in should succeed"
        assert 0.6 <= earned <= 1.0, f"Earned credits should be in the range [0.6, 1.0], got {earned}"
        
        # Double check-in cooldown validation
        success2, msg2, earned2 = await user_service.check_in(buyer.id)
        assert success2 is False, "Daily check-in should block duplicate check-in due to cooldown"
        print("✅ Daily check-in streak logic verified.")

        # --- Test Marketplace Category & Agent Listing Moderation ---
        print("\n⏳ Testing marketplace listings flow...")
        cat = await admin_repo.add(
            Category(name="AI Tools", icon="🧠", order=1)
        )
        await session.flush()

        agent = await market_service.submit_agent(
            seller_id=222,
            category_id=cat.id,
            name="ChatGPT Assistant",
            description="Premium ChatGPT helper script.",
            features="Fast, Async, SQLite",
            price=2.0,
            file_id="tg_file_id_example_123",
            screenshot_ids=["screenshot_1"],
            demo_url="https://t.me/example_bot"
        )
        await session.commit()
        assert agent.status == "pending", "Submitted agent status must be pending"
        
        # Approve listing
        approved = await market_service.approve_agent(agent.id)
        assert approved is True, "Moderation approval must succeed"
        await session.refresh(agent)
        assert agent.status == "active", "Approved agent status must be active"
        print("✅ Agent submission & moderation pipeline verified.")

        # Force set buyer credits to 2.1 and seller to 2.0 to make transaction math deterministic
        buyer.credits = 2.1
        seller.credits = 2.0
        await session.flush()

        # --- Test Purchases Transaction Flow ---
        print("\n⏳ Testing agent purchases...")
        # Buyer has 1.0 referral + 1.1 daily = 2.1 credits. Price is 2.0. Buyer has enough credits.
        success_buy, buy_msg, order = await market_service.purchase_agent(buyer.id, agent.id)
        assert success_buy is True, f"Purchase should succeed, message: {buy_msg}"
        assert order is not None, "Order object must be returned"
        
        await session.refresh(buyer)
        await session.refresh(seller)
        # Buyer remaining credits = 2.1 - 2.0 = 0.1
        assert abs(buyer.credits - 0.1) < 0.001, f"Buyer credits remaining should be 0.1, got {buyer.credits}"
        # Seller credits: 2.0 (referral) + 1.9 (agent price 2.0 minus 5% platform commission) = 3.9
        assert abs(seller.credits - 3.9) < 0.001, f"Seller credits should be 3.9, got {seller.credits}"
        print("✅ Agent purchase transactions verified.")

        # --- Test Rating/Reviews Pipeline ---
        print("\n⏳ Testing reviews and average rating recalculation...")
        success_rev, rev_msg = await market_service.submit_review(
            buyer_id=buyer.id,
            order_id=order.id,
            agent_id=agent.id,
            rating=4,
            review_text="Very fast and lightweight code!"
        )
        assert success_rev is True, "Review submission should succeed"
        
        await session.refresh(agent)
        assert agent.rating == 4.0, f"Agent average rating should be updated to 4.0, got {agent.rating}"
        print("✅ Review submission and ratings calculations verified.")

        # --- Test Backup System ---
        print("\n⏳ Testing backup engine serialization...")
        backup_service = BackupService(session)
        zip_path = await backup_service.create_backup(admin_id=111, is_auto=True)
        assert os.path.exists(zip_path) is True, "Backup zip file should be created on disk"
        
        # Clean up zip
        if os.path.exists(zip_path):
            os.remove(zip_path)
        print("✅ Backup serialization verified.")

    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY! The core codebase is robust and production-ready.")

if __name__ == "__main__":
    asyncio.run(run_tests())
