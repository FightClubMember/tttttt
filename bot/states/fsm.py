# FSM State Constants for ConversationHandlers

# Sell Agent States
(
    SELL_NAME,
    SELL_CATEGORY,
    SELL_DESCRIPTION,
    SELL_FEATURES,
    SELL_PRICE,
    SELL_DEMO,
    SELL_FILE,
    SELL_SCREENSHOTS,
    SELL_NOTES
) = range(100, 109)

# Category CRUD States
(
    ADD_CAT_NAME,
    ADD_CAT_ICON,
    ADD_CAT_BANNER
) = range(200, 203)

# Support Ticket States
(
    TICKET_SUBJECT,
    TICKET_MESSAGE,
    TICKET_REPLY
) = range(300, 303)

# Admin Panel input states
(
    ADMIN_USER_SEARCH,
    ADMIN_ADD_CREDITS,
    ADMIN_REMOVE_CREDITS,
    ADMIN_WARN_USER,
    ADMIN_BROADCAST_GET_MSG,
    ADMIN_ADD_CHANNEL,
    ADMIN_COUPON_NAME,
    ADMIN_COUPON_REWARD,
    ADMIN_COUPON_EXPIRY,
    ADMIN_COUPON_USES
) = range(400, 410)

# Review agent submission state
(
    REVIEW_SUBMIT_STARS,
    REVIEW_SUBMIT_TEXT
) = range(500, 502)
