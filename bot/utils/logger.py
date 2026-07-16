import os
import sys
from loguru import logger

# Create log directories inside root
os.makedirs("logs", exist_ok=True)

# Remove default basic logger
logger.remove()

# Output to console with color coding
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:7}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

# Output to rotating logs file
logger.add(
    "logs/bot.log",
    rotation="10 MB",
    retention="14 days",
    compression="zip",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:7} | {name}:{function}:{line} - {message}",
    level="DEBUG"
)

def log_audit(user_id: int, action: str, details: str):
    """Formats and writes a security audit statement."""
    logger.info(f"[AUDIT-LOG] Admin/User: {user_id} | Action: {action} | Details: {details}")
