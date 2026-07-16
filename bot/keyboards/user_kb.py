from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from bot.models.agent import Category, Agent
from bot.models.settings import ForceJoinChannel

class UserKeyboards:
    @staticmethod
    def main_menu(unread_notifs: int = 0, is_admin: bool = False) -> InlineKeyboardMarkup:
        """Returns the main menu grid keyboard (excluding items on reply keyboard)."""
        notif_label = f"🔔 Notifications ({unread_notifs})" if unread_notifs > 0 else "🔔 Notifications"
        
        keyboard = [
            [
                InlineKeyboardButton("⭐ Favorites", callback_data="user_menu:favorites"),
                InlineKeyboardButton("❤️ Wishlist", callback_data="user_menu:wishlist")
            ],
            [
                InlineKeyboardButton(notif_label, callback_data="user_menu:notifications"),
                InlineKeyboardButton("🎟 Coupons", callback_data="user_menu:coupons")
            ],
            [
                InlineKeyboardButton("⚙ Settings", callback_data="user_menu:settings"),
                InlineKeyboardButton("ℹ About", callback_data="user_menu:about")
            ]
        ]
        
        if is_admin:
            keyboard.append([InlineKeyboardButton("🛠 Admin Panel", callback_data="admin:dashboard")])
            
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def wallet_menu() -> InlineKeyboardMarkup:
        """Returns wallet action keyboard."""
        keyboard = [
            [InlineKeyboardButton("🎟 Redeem Coupon", callback_data="wallet:redeem_coupon")],
            [InlineKeyboardButton("📊 Export Statement (CSV)", callback_data="wallet:export_statement")],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="user_menu:main")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def force_join(missing_channels: List[ForceJoinChannel]) -> InlineKeyboardMarkup:
        """Dynamically generates buttons to join missing channels and verify."""
        keyboard = []
        for idx, chan in enumerate(missing_channels, 1):
            url = chan.invite_link
            if not url and chan.channel_username:
                username_clean = chan.channel_username.lstrip("@")
                url = f"https://t.me/{username_clean}"
            
            keyboard.append([InlineKeyboardButton(f"📢 Join Channel {idx}", url=url)])
            
        keyboard.append([
            InlineKeyboardButton("✅ Verify", callback_data="force_join:verify"),
            InlineKeyboardButton("🔄 Refresh", callback_data="force_join:refresh")
        ])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def categories_list(categories: List[Category], back_callback: str = "user_menu:main") -> InlineKeyboardMarkup:
        """Generates list of categories."""
        keyboard = []
        # Display 2 categories per row
        row = []
        for cat in categories:
            row.append(InlineKeyboardButton(f"{cat.icon} {cat.name}", callback_data=f"catalog:cat:{cat.id}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
            
        # Add Search button
        keyboard.append([InlineKeyboardButton("🔍 Search Catalog", callback_data="catalog:search")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=back_callback)])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def agents_list(agents: List[Agent], category_id: int) -> InlineKeyboardMarkup:
        """Generates list of active agents in a category."""
        keyboard = []
        for agent in agents:
            # Indicate trending/pinned
            prefix = "📌 " if agent.is_pinned else "🔥 " if agent.is_trending else "📦 "
            keyboard.append([InlineKeyboardButton(f"{prefix}{agent.name} | {agent.price} Credits", callback_data=f"catalog:agent:{agent.id}")])
            
        keyboard.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="user_menu:buy")])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def main_reply_keyboard() -> ReplyKeyboardMarkup:
        """Returns the persistent bottom reply keyboard."""
        return ReplyKeyboardMarkup([
            ["🛒 Buy Agent", "📤 Sell Agent"],
            ["👛 Wallet", "👥 Referral"],
            ["🆘 Support", "🚩 Report", "🎁 Claim"]
        ], resize_keyboard=True)

    @staticmethod
    def agent_details(agent_id: int, is_fav: bool = False, is_wl: bool = False) -> InlineKeyboardMarkup:
        """Generates buttons for agent details card."""
        fav_text = "⭐ Remove Favorite" if is_fav else "⭐ Favorite"
        wl_text = "❤️ Remove Wishlist" if is_wl else "❤️ Wishlist"
        
        keyboard = [
            [InlineKeyboardButton("💎 Buy Agent", callback_data=f"catalog:terms:{agent_id}")],
            [
                InlineKeyboardButton(fav_text, callback_data=f"catalog:toggle_fav:{agent_id}"),
                InlineKeyboardButton(wl_text, callback_data=f"catalog:toggle_wl:{agent_id}")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="catalog:back_to_list")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def terms_and_conditions(agent_id: int) -> InlineKeyboardMarkup:
        """Terms and Conditions acceptance options before checkout."""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Accept & Buy", callback_data=f"catalog:tc_accept:{agent_id}")],
            [InlineKeyboardButton("❌ Decline", callback_data=f"catalog:agent:{agent_id}")]
        ])

    @staticmethod
    def download_agent(file_id: str, agent_id: int) -> InlineKeyboardMarkup:
        """Renders review options after purchase or in order history."""
        keyboard = [
            [InlineKeyboardButton("📥 Download Agent Code", callback_data=f"catalog:download:{agent_id}")],
            [InlineKeyboardButton("⭐ Rate & Review", callback_data=f"catalog:review:{agent_id}")],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="user_menu:main")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def rating_stars(agent_id: int) -> InlineKeyboardMarkup:
        """Grid of stars 1-5 for ratings."""
        keyboard = [[
            InlineKeyboardButton("⭐", callback_data=f"catalog:rate:{agent_id}:1"),
            InlineKeyboardButton("⭐⭐", callback_data=f"catalog:rate:{agent_id}:2"),
            InlineKeyboardButton("⭐⭐⭐", callback_data=f"catalog:rate:{agent_id}:3"),
            InlineKeyboardButton("⭐⭐⭐⭐", callback_data=f"catalog:rate:{agent_id}:4"),
            InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"catalog:rate:{agent_id}:5")
        ], [InlineKeyboardButton("🚫 Skip review", callback_data="user_menu:main")]]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def back_to_main() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main", callback_data="user_menu:main")]])
