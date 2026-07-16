from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Import all handler components
from bot.handlers.user.base import (
    start_command, verify_join_callback, menu_navigation_callback,
    reply_keyboard_routing_handler, view_notifications_callback
)
from bot.handlers.user.wallet import wallet_menu_callback, referral_menu_callback, export_statement_callback, coupon_conv_handler, coupon_start_callback
from bot.handlers.user.check_in import check_in_callback
from bot.handlers.user.marketplace import (
    categories_list_callback, category_agents_callback, agent_details_callback,
    agent_terms_callback, buy_agent_callback, download_file_callback, toggle_fav_callback, 
    toggle_wl_callback, view_favorites_callback, view_wishlist_callback, search_conv_handler, 
    review_conv_handler
)
from bot.handlers.support.ticket import support_menu_callback, view_ticket_callback, close_ticket_callback, ticket_conv_handler, ticket_create_start_callback
from bot.handlers.seller.register import seller_conv_handler, seller_register_start_callback
from bot.handlers.admin.dashboard import admin_dashboard_callback, stats_view_callback, admin_close_callback, admin_command_handler
from bot.handlers.admin.users import (
    admin_users_menu_callback, usract_routing_callback, otp_callback_handler,
    users_search_conv, credits_adj_conv, warn_user_conv
)
from bot.handlers.admin.items import (
    admin_categories_callback, admin_category_edit_callback,
    admin_moderation_queue_callback, admin_inspect_agent_callback,
    admin_reject_agent_callback, admin_moderation_conv
)
from bot.handlers.admin.force_join import (
    admin_force_join_menu_callback, admin_channel_edit_callback,
    admin_toggle_channel_callback, admin_delete_channel_callback, channel_add_conv
)
from bot.handlers.admin.broadcast import (
    admin_broadcast_menu_callback, admin_broadcast_cancel_callback,
    broadcast_confirm_send_callback, broadcast_conv
)
from bot.handlers.admin.settings import (
    admin_settings_menu_callback, admin_toggle_maintenance_callback,
    admin_backups_menu_callback, admin_create_backup_callback, backup_restore_conv
)

def register_all_handlers(application: Application):
    """Registers all bot handlers systematically to the application."""
    
    # 1. Command Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", admin_command_handler))
    
    # Fallback command handlers for direct access
    application.add_handler(CommandHandler("buy", categories_list_callback))
    application.add_handler(CommandHandler("sell", seller_register_start_callback))
    application.add_handler(CommandHandler("wallet", wallet_menu_callback))
    application.add_handler(CommandHandler("referral", referral_menu_callback))
    application.add_handler(CommandHandler("support", support_menu_callback))
    application.add_handler(CommandHandler("report", ticket_create_start_callback))
    application.add_handler(CommandHandler("coupons", coupon_start_callback))

    # 2. Reply Keyboard button click MessageHandler (High Priority)
    # Intercepts navigation buttons to break users out of stuck FSMs immediately
    reply_keyboard_buttons = [
        "🛒 Buy Agent", "📤 Sell Agent", "👛 Wallet", "👥 Referral",
        "🆘 Support", "🚩 Report", "🎟 Coupons"
    ]
    application.add_handler(
        MessageHandler(
            filters.Regex("^(🛒 Buy Agent|📤 Sell Agent|👛 Wallet|👥 Referral|🆘 Support|🚩 Report|🎟 Coupons)$") |
            filters.Text(reply_keyboard_buttons),
            reply_keyboard_routing_handler
        )
    )

    # 3. Conversation FSM Handlers (higher priority first)
    application.add_handler(seller_conv_handler)
    application.add_handler(ticket_conv_handler)
    application.add_handler(coupon_conv_handler)
    application.add_handler(search_conv_handler)
    application.add_handler(review_conv_handler)
    
    # Admin FSM conversations
    application.add_handler(users_search_conv)
    application.add_handler(credits_adj_conv)
    application.add_handler(warn_user_conv)
    application.add_handler(channel_add_conv)
    application.add_handler(broadcast_conv)
    application.add_handler(backup_restore_conv)
    application.add_handler(admin_moderation_conv)

    # 4. Base navigation callbacks
    application.add_handler(CallbackQueryHandler(verify_join_callback, pattern="^force_join:verify$"))
    application.add_handler(CallbackQueryHandler(verify_join_callback, pattern="^force_join:refresh$"))
    application.add_handler(CallbackQueryHandler(menu_navigation_callback, pattern="^user_menu:(main|about|settings)$"))

    # 5. User flow callbacks
    application.add_handler(CallbackQueryHandler(wallet_menu_callback, pattern="^user_menu:wallet$"))
    application.add_handler(CallbackQueryHandler(referral_menu_callback, pattern="^user_menu:referral$"))
    application.add_handler(CallbackQueryHandler(export_statement_callback, pattern="^wallet:export_statement$"))
    application.add_handler(CallbackQueryHandler(check_in_callback, pattern="^user_menu:checkin$"))
    application.add_handler(CallbackQueryHandler(support_menu_callback, pattern="^user_menu:support$"))
    application.add_handler(CallbackQueryHandler(view_favorites_callback, pattern="^user_menu:favorites$"))
    application.add_handler(CallbackQueryHandler(view_wishlist_callback, pattern="^user_menu:wishlist$"))
    application.add_handler(CallbackQueryHandler(view_notifications_callback, pattern="^user_menu:notifications$"))

    # 6. Catalog callbacks
    application.add_handler(CallbackQueryHandler(categories_list_callback, pattern="^user_menu:buy$"))
    application.add_handler(CallbackQueryHandler(category_agents_callback, pattern="^catalog:cat:\\d+$"))
    application.add_handler(CallbackQueryHandler(agent_details_callback, pattern="^catalog:agent:\\d+$"))
    application.add_handler(CallbackQueryHandler(agent_terms_callback, pattern="^catalog:terms:\\d+$"))
    application.add_handler(CallbackQueryHandler(buy_agent_callback, pattern="^catalog:tc_accept:\\d+$"))
    application.add_handler(CallbackQueryHandler(download_file_callback, pattern="^catalog:download:\\d+$"))
    application.add_handler(CallbackQueryHandler(toggle_fav_callback, pattern="^catalog:toggle_fav:\\d+$"))
    application.add_handler(CallbackQueryHandler(toggle_wl_callback, pattern="^catalog:toggle_wl:\\d+$"))

    # 7. Ticket management callbacks
    application.add_handler(CallbackQueryHandler(view_ticket_callback, pattern="^ticket:view:\\d+$"))
    application.add_handler(CallbackQueryHandler(close_ticket_callback, pattern="^ticket:close:\\d+$"))

    # 8. Admin control panel callbacks
    application.add_handler(CallbackQueryHandler(admin_dashboard_callback, pattern="^admin:dashboard$"))
    application.add_handler(CallbackQueryHandler(admin_close_callback, pattern="^admin:close$"))
    application.add_handler(CallbackQueryHandler(stats_view_callback, pattern="^admin:menu:stats$"))
    
    # Admin users callbacks
    application.add_handler(CallbackQueryHandler(admin_users_menu_callback, pattern="^admin:menu:users$"))
    application.add_handler(CallbackQueryHandler(usract_routing_callback, pattern="^admin:usract:\\w+:\\d+$"))
    application.add_handler(CallbackQueryHandler(otp_callback_handler, pattern="^otp:\\w+:[\\w:]+$"))

    # Admin items callbacks
    application.add_handler(CallbackQueryHandler(admin_categories_callback, pattern="^admin:menu:categories$"))
    application.add_handler(CallbackQueryHandler(admin_category_edit_callback, pattern="^admin:cat:edit:\\d+$"))
    application.add_handler(CallbackQueryHandler(admin_moderation_queue_callback, pattern="^admin:menu:agents$"))
    application.add_handler(CallbackQueryHandler(admin_inspect_agent_callback, pattern="^admin:mod:inspect:\\d+$"))
    application.add_handler(CallbackQueryHandler(admin_reject_agent_callback, pattern="^admin:modact:reject:\\d+$"))

    # Admin force join callbacks
    application.add_handler(CallbackQueryHandler(admin_force_join_menu_callback, pattern="^admin:menu:forcejoin$"))
    application.add_handler(CallbackQueryHandler(admin_channel_edit_callback, pattern="^admin:fj:edit:\\d+$"))
    application.add_handler(CallbackQueryHandler(admin_toggle_channel_callback, pattern="^admin:fjact:toggle:\\d+$"))
    application.add_handler(CallbackQueryHandler(admin_delete_channel_callback, pattern="^admin:fjact:delete:\\d+$"))

    # Admin broadcast callbacks
    application.add_handler(CallbackQueryHandler(admin_broadcast_menu_callback, pattern="^admin:menu:broadcast$"))
    application.add_handler(CallbackQueryHandler(broadcast_confirm_send_callback, pattern="^admin:broadcast:confirm_send$"))
    application.add_handler(CallbackQueryHandler(admin_broadcast_cancel_callback, pattern="^admin:broadcast:cancel:\\d+$"))

    # Admin settings & backups callbacks
    application.add_handler(CallbackQueryHandler(admin_settings_menu_callback, pattern="^admin:menu:settings$"))
    application.add_handler(CallbackQueryHandler(admin_toggle_maintenance_callback, pattern="^admin:settings:toggle_maintenance$"))
    application.add_handler(CallbackQueryHandler(admin_backups_menu_callback, pattern="^admin:menu:backups$"))
    application.add_handler(CallbackQueryHandler(admin_create_backup_callback, pattern="^admin:backups:create$"))
