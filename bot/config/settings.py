import os
from dotenv import load_dotenv

# Load local .env file
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data.db")
REDIS_URL = os.getenv("REDIS_URL", "")

# Parse cache configurations
try:
    CACHE_TTL = int(os.getenv("CACHE_TTL", 300))
except ValueError:
    CACHE_TTL = 300

# Parse admins list
admin_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = set()
if admin_raw:
    for aid in admin_raw.split(","):
        aid = aid.strip()
        if aid.isdigit():
            ADMIN_IDS.add(int(aid))

# Bot defaults
DEFAULT_BOT_NAME = os.getenv("BOT_NAME", "Money Agent Marketplace")
DEFAULT_CURRENCY_NAME = os.getenv("CURRENCY_NAME", "Credits")
DEFAULT_SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "support")

# Security and system parameters
try:
    OTP_EXPIRY_SECONDS = int(os.getenv("OTP_EXPIRY_SECONDS", 120))
except ValueError:
    OTP_EXPIRY_SECONDS = 120

try:
    RATE_LIMIT_COOLDOWN = float(os.getenv("RATE_LIMIT_COOLDOWN", 0.5))
except ValueError:
    RATE_LIMIT_COOLDOWN = 0.5

# Ensure critical variables are set (will print warnings if missing, but let it boot for config verification)
if not BOT_TOKEN:
    print("[WARNING] BOT_TOKEN env variable is missing! The bot will fail to start.")
