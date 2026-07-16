import datetime
from typing import List, Any
from bot.models.agent import Order

class Formatter:
    @staticmethod
    def format_date(dt: datetime.datetime) -> str:
        """Formats datetime objects consistently."""
        if not dt:
            return "N/A"
        return dt.strftime("%Y-%m-%d %H:%M UTC")

    @staticmethod
    def format_invoice(order: Order) -> str:
        """Compiles a premium invoice for the user."""
        receipt = f"📄 <b>INVOICE #{order.id}</b>\n"
        receipt += f"📅 Date: {Formatter.format_date(order.purchased_at)}\n"
        receipt += f"👤 Buyer ID: <code>{order.buyer_id}</code>\n"
        receipt += f"────────────────────\n"
        
        for idx, item in enumerate(order.items, 1):
            receipt += f"{idx}. 📦 <b>{item.agent.name}</b>\n"
            receipt += f"   💰 Cost: {item.price} Credits\n"
            receipt += f"   🏷 Version: v{item.agent.version}\n"
            
        receipt += f"────────────────────\n"
        receipt += f"💎 <b>Total Paid: {order.total_credits} Credits</b>\n"
        receipt += f"✅ Status: <b>{order.status.upper()}</b>\n"
        return receipt

    @staticmethod
    def generate_statement_csv(user_id: int, orders: List[Any], sales: List[Any]) -> str:
        """Creates a CSV text representation of transactions for account statements."""
        csv_lines = ["Date,Type,Item ID,Item Name,Price (Credits),Status"]
        
        # Add purchases
        for order in orders:
            for item in order.items:
                date_str = Formatter.format_date(order.purchased_at)
                csv_lines.append(f'"{date_str}","Purchase","{item.agent.id}","{item.agent.name}",-{item.price},"{order.status}"')
                
        # Add sales
        for sale_item in sales:
            # sale_item is an OrderItem where agent.seller_id == user_id
            date_str = Formatter.format_date(sale_item.order.purchased_at)
            csv_lines.append(f'"{date_str}","Sale","{sale_item.agent.id}","{sale_item.agent.name}",+{sale_item.price},"{sale_item.order.status}"')
            
        return "\n".join(csv_lines)
