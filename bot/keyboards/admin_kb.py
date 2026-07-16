from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.models.settings import ForceJoinChannel, Coupon
from bot.models.agent import Category, Agent

class AdminKeyboards:
    @staticmethod
    def dashboard() -> InlineKeyboardMarkup:
        """Main admin control center keyboard."""
        keyboard = [
            [
                InlineKeyboardButton("👥 Users", callback_data="admin:menu:users"),
                InlineKeyboardButton("💰 Credits", callback_data="admin:menu:credits")
            ],
            [
                InlineKeyboardButton("📦 Agents Queue", callback_data="admin:menu:agents"),
                InlineKeyboardButton("📂 Categories", callback_data="admin:menu:categories")
            ],
            [
                InlineKeyboardButton("🎟 Coupons", callback_data="admin:menu:coupons"),
                InlineKeyboardButton("📢 Force Join", callback_data="admin:menu:forcejoin")
            ],
            [
                InlineKeyboardButton("📣 Broadcast", callback_data="admin:menu:broadcast"),
                InlineKeyboardButton("⚙ Settings", callback_data="admin:menu:settings")
            ],
            [
                InlineKeyboardButton("💾 Backups & Logs", callback_data="admin:menu:backups"),
                InlineKeyboardButton("📊 Statistics", callback_data="admin:menu:stats")
            ],
            [InlineKeyboardButton("❌ Close Panel", callback_data="admin:close")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def back_to_dash() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin:dashboard")]])

    @staticmethod
    def users_menu() -> InlineKeyboardMarkup:
        """User management initial keyboard."""
        keyboard = [
            [InlineKeyboardButton("🔍 Search User (ID/User)", callback_data="admin:users:search")],
            [InlineKeyboardButton("📋 View All Users", callback_data="admin:users:all")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin:dashboard")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def user_action_sheet(user_id: int, is_banned: bool = False, is_black: bool = False) -> InlineKeyboardMarkup:
        """Comprehensive management list for specific users."""
        ban_text = "🟢 Unban User" if is_banned else "🔴 Ban User"
        black_text = "🟢 Whitelist User" if is_black else "⚫ Blacklist User"
        
        keyboard = [
            [
                InlineKeyboardButton("➕ Add Credits", callback_data=f"admin:usract:add_cr:{user_id}"),
                InlineKeyboardButton("➖ Remove Credits", callback_data=f"admin:usract:rem_cr:{user_id}")
            ],
            [
                InlineKeyboardButton("⚠️ Issue Warning", callback_data=f"admin:usract:warn:{user_id}"),
                InlineKeyboardButton("🔄 Reset Wallet", callback_data=f"admin:usract:reset_wal:{user_id}")
            ],
            [
                InlineKeyboardButton(ban_text, callback_data=f"admin:usract:toggle_ban:{user_id}"),
                InlineKeyboardButton(black_text, callback_data=f"admin:usract:toggle_black:{user_id}")
            ],
            [InlineKeyboardButton("❌ Delete Account", callback_data=f"admin:usract:delete:{user_id}")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin:menu:users")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def credits_menu() -> InlineKeyboardMarkup:
        """Credit settings controls."""
        keyboard = [
            [
                InlineKeyboardButton("➕ Bulk Add Credits", callback_data="admin:credits:bulk_add"),
                InlineKeyboardButton("➖ Bulk Remove Credits", callback_data="admin:credits:bulk_rem")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="admin:dashboard")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def categories_menu(categories: List[Category]) -> InlineKeyboardMarkup:
        """Categories CRUD listing."""
        keyboard = []
        for cat in categories:
            keyboard.append([InlineKeyboardButton(f"⚙️ {cat.icon} {cat.name}", callback_data=f"admin:cat:edit:{cat.id}")])
            
        keyboard.append([InlineKeyboardButton("➕ Create Category", callback_data="admin:cat:create")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin:dashboard")])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def category_edit(cat_id: int) -> InlineKeyboardMarkup:
        """Category specific actions."""
        keyboard = [
            [InlineKeyboardButton("✏️ Rename Category", callback_data=f"admin:catact:rename:{cat_id}")],
            [
                InlineKeyboardButton("🎭 Edit Icon", callback_data=f"admin:catact:icon:{cat_id}"),
                InlineKeyboardButton("🖼 Upload Banner", callback_data=f"admin:catact:banner:{cat_id}")
            ],
            [InlineKeyboardButton("🗑 Delete Category", callback_data=f"admin:catact:delete:{cat_id}")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin:menu:categories")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def force_join_menu(channels: List[ForceJoinChannel]) -> InlineKeyboardMarkup:
        """Force Join controls."""
        keyboard = []
        for chan in channels:
            status_emoji = "🟢" if chan.is_active else "🔴"
            label = f"{status_emoji} {chan.channel_username or f'ID: {chan.id}'}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"admin:fj:edit:{chan.id}")])
            
        keyboard.append([InlineKeyboardButton("➕ Add Channel", callback_data="admin:fj:add")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin:dashboard")])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def force_join_edit(chan_id: int, is_active: bool) -> InlineKeyboardMarkup:
        """Channel specific actions."""
        toggle_text = "🔴 Disable Channel" if is_active else "🟢 Enable Channel"
        keyboard = [
            [InlineKeyboardButton(toggle_text, callback_data=f"admin:fjact:toggle:{chan_id}")],
            [InlineKeyboardButton("🧪 Test Verification", callback_data=f"admin:fjact:test:{chan_id}")],
            [InlineKeyboardButton("🗑 Delete Channel", callback_data=f"admin:fjact:delete:{chan_id}")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin:menu:forcejoin")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def broadcast_menu() -> InlineKeyboardMarkup:
        """Broadcast parameters target selectors."""
        keyboard = [
            [InlineKeyboardButton("🌍 Target: All Users", callback_data="admin:broadcast:start:all")],
            [InlineKeyboardButton("🛠 Target: Admins", callback_data="admin:broadcast:start:admins")],
            [InlineKeyboardButton("📤 Target: Sellers", callback_data="admin:broadcast:start:sellers")],
            [InlineKeyboardButton("🛒 Target: Buyers", callback_data="admin:broadcast:start:buyers")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin:dashboard")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def broadcast_running(broadcast_id: int) -> InlineKeyboardMarkup:
        """Renders action buttons during a live broadcast."""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🚫 Cancel Broadcast", callback_data=f"admin:broadcast:cancel:{broadcast_id}")]
        ])

    @staticmethod
    def settings_menu() -> InlineKeyboardMarkup:
        """Global config keys updater."""
        keyboard = [
            [InlineKeyboardButton("👥 Referral Reward", callback_data="admin:settings:edit:referral_reward")],
            [InlineKeyboardButton("🎁 Daily Check-in Reward", callback_data="admin:settings:edit:daily_reward")],
            [InlineKeyboardButton("🎉 Welcome Reward", callback_data="admin:settings:edit:welcome_reward")],
            [InlineKeyboardButton("🔧 Toggle Maintenance Mode", callback_data="admin:settings:toggle_maintenance")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin:dashboard")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def backups_menu() -> InlineKeyboardMarkup:
        """Database backup dashboard."""
        keyboard = [
            [InlineKeyboardButton("💾 Create Manual Backup", callback_data="admin:backups:create")],
            [InlineKeyboardButton("📂 Upload & Restore Backup", callback_data="admin:backups:restore")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin:dashboard")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def moderation_queue(agents: List[Agent]) -> InlineKeyboardMarkup:
        """Moderation queue listing keyboard."""
        keyboard = []
        for agent in agents:
            keyboard.append([InlineKeyboardButton(f"🔎 {agent.name} | {agent.price} Credits", callback_data=f"admin:mod:inspect:{agent.id}")])
            
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin:dashboard")])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def moderation_inspect(agent_id: int) -> InlineKeyboardMarkup:
        """Inspect moderation queue listing actions."""
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve Listing", callback_data=f"admin:modact:approve:{agent_id}"),
                InlineKeyboardButton("❌ Reject Listing", callback_data=f"admin:modact:reject:{agent_id}")
            ],
            [InlineKeyboardButton("✏️ Edit Price", callback_data=f"admin:modact:edit_price:{agent_id}")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin:menu:agents")]
        ]
        return InlineKeyboardMarkup(keyboard)
