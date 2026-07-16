from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.models.agent import Category

class SellerKeyboards:
    @staticmethod
    def cancel_submission() -> InlineKeyboardMarkup:
        """Button to cancel the current agent creation FSM flow."""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🚫 Cancel Submission", callback_data="seller_flow:cancel")]
        ])

    @staticmethod
    def category_select(categories: List[Category]) -> InlineKeyboardMarkup:
        """Lists categories for selection during listing FSM flow."""
        keyboard = []
        for cat in categories:
            keyboard.append([InlineKeyboardButton(f"{cat.icon} {cat.name}", callback_data=f"seller_flow:cat:{cat.id}")])
        keyboard.append([InlineKeyboardButton("🚫 Cancel", callback_data="seller_flow:cancel")])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def skipped_field(field_name: str) -> InlineKeyboardMarkup:
        """Provides optional fields skipping during submission FSM."""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⏭ Skip {field_name}", callback_data=f"seller_flow:skip:{field_name}")],
            [InlineKeyboardButton("🚫 Cancel", callback_data="seller_flow:cancel")]
        ])
