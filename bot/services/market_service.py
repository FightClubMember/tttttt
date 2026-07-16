import json
from typing import Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from bot.repositories.user_repo import UserRepository
from bot.repositories.agent_repo import AgentRepository
from bot.repositories.admin_repo import AdminRepository
from bot.models.agent import Agent, Order, OrderItem

class MarketplaceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.agent_repo = AgentRepository(session)
        self.admin_repo = AdminRepository(session)

    async def submit_agent(
        self,
        seller_id: int,
        category_id: int,
        name: str,
        description: str,
        features: str,
        price: float,
        file_id: str,
        screenshot_ids: List[str],
        demo_url: Optional[str] = None,
        extra_notes: Optional[str] = None,
        version: str = "1.0.0"
    ) -> Agent:
        """Creates a pending agent submission for moderation."""
        screenshots_json = json.dumps(screenshot_ids) if screenshot_ids else "[]"
        agent = Agent(
            category_id=category_id,
            seller_id=seller_id,
            name=name,
            description=description,
            features=features,
            price=price,
            file_id=file_id,
            screenshot_ids=screenshots_json,
            demo_url=demo_url,
            extra_notes=extra_notes,
            version=version,
            status="pending"
        )
        await self.agent_repo.add(agent)
        await self.session.commit()
        return agent

    async def approve_agent(self, agent_id: int) -> bool:
        """Approves a pending agent listing."""
        agent = await self.agent_repo.get_agent(agent_id)
        if not agent or agent.status != "pending":
            return False
            
        agent.status = "active"
        
        # Notify seller
        await self.admin_repo.add_notification(
            agent.seller_id,
            f"✅ Your agent submission '{agent.name}' has been approved and published!"
        )
        await self.session.commit()
        return True

    async def reject_agent(self, agent_id: int) -> bool:
        """Rejects a pending agent listing."""
        agent = await self.agent_repo.get_agent(agent_id)
        if not agent or agent.status != "pending":
            return False
            
        agent.status = "rejected"
        
        # Notify seller
        await self.admin_repo.add_notification(
            agent.seller_id,
            f"❌ Your agent submission '{agent.name}' was rejected by moderators."
        )
        await self.session.commit()
        return True

    async def purchase_agent(self, buyer_id: int, agent_id: int) -> Tuple[bool, str, Optional[Order]]:
        """
        Processes agent purchase transactions using credits.
        Returns (success, message, order_object)
        """
        buyer = await self.user_repo.get_user(buyer_id)
        if not buyer:
            return False, "Buyer profile not found.", None

        agent = await self.agent_repo.get_agent(agent_id)
        if not agent or agent.status != "active":
            return False, "Agent listing is no longer active.", None

        # Self purchase check
        if agent.seller_id == buyer_id:
            return False, "❌ You cannot purchase your own agent listing.", None

        # Check stock
        if agent.stock == 0:
            return False, "❌ This agent is currently out of stock.", None

        # Check credits
        if buyer.credits < agent.price:
            return False, "❌ Insufficient credits. Earn credits via Referral or Daily rewards, or contact admins.", None

        # Load seller
        seller = await self.user_repo.get_user(agent.seller_id)
        if not seller:
            return False, "Seller profile not found.", None

        # Determine optional platform commission (e.g. 5%)
        commission_str = await self.admin_repo.get_setting("commission_rate")
        commission_rate = float(commission_str) if commission_str else 0.05
        
        seller_share = agent.price * (1.0 - commission_rate)

        # Deduct credits from buyer
        buyer.credits -= agent.price
        buyer.lifetime_spent += agent.price

        # Add credits to seller
        seller.credits += seller_share
        seller.sold_credits += seller_share
        seller.lifetime_earned += seller_share

        # Decrement stock if limited
        if agent.stock > 0:
            agent.stock -= 1

        agent.downloads += 1

        # Create Order
        order = Order(buyer_id=buyer_id, total_credits=agent.price, status="completed")
        await self.agent_repo.add(order)
        await self.session.flush() # Populate order ID

        # Create Order Item
        item = OrderItem(order_id=order.id, agent_id=agent.id, price=agent.price)
        await self.agent_repo.add(item)

        # Notifications
        await self.admin_repo.add_notification(
            buyer_id, 
            f"🛒 Purchase successful! You bought '{agent.name}' for {agent.price} Credits. Check your Order history to download."
        )
        await self.admin_repo.add_notification(
            agent.seller_id, 
            f"💰 Agent Sold! Someone purchased '{agent.name}'. Received +{seller_share} Credits (after commission)."
        )

        await self.session.commit()
        return True, "Success", order

    async def submit_review(self, buyer_id: int, order_id: int, agent_id: int, rating: int, review_text: str) -> Tuple[bool, str]:
        """Submits or edits user reviews/stars."""
        # Find order item belonging to buyer
        order = await self.agent_repo.get_order(order_id)
        if not order or order.buyer_id != buyer_id:
            return False, "Purchase record not found."

        target_item = None
        for item in order.items:
            if item.agent_id == agent_id:
                target_item = item
                break

        if not target_item:
            return False, "Item not found in this order."

        # Save review details
        import datetime
        target_item.rating = rating
        target_item.review_text = review_text
        target_item.rated_at = datetime.datetime.utcnow()

        await self.session.flush()
        # Recalculate average rating on the Agent table
        await self.agent_repo.update_agent_rating(agent_id)
        
        await self.session.commit()
        return True, "Review submitted successfully!"
