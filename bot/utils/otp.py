import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class OTPProvider:
    @staticmethod
    def generate_code() -> str:
        """Generates a 4-digit numeric code."""
        return "".join(str(random.randint(0, 9)) for _ in range(4))

    @staticmethod
    def get_otp_keyboard(action_name: str, target_id: str, current_input: str = "") -> InlineKeyboardMarkup:
        """
        Creates the inline keyboard grid for OTP entry.
        Callback format: otp:<action>:<target>:<digits_so_far>:<pressed_val>
        """
        grid = []
        row = []
        for i in range(1, 10):
            row.append(InlineKeyboardButton(str(i), callback_data=f"otp:{action_name}:{target_id}:{current_input}:{i}"))
            if len(row) == 3:
                grid.append(row)
                row = []
                
        # Zero, Clear, Cancel row
        grid.append([
            InlineKeyboardButton("❌ Clear", callback_data=f"otp:{action_name}:{target_id}:{current_input}:clear"),
            InlineKeyboardButton("0", callback_data=f"otp:{action_name}:{target_id}:{current_input}:0"),
            InlineKeyboardButton("🚫 Cancel", callback_data=f"otp:{action_name}:{target_id}:{current_input}:cancel")
        ])
        
        return InlineKeyboardMarkup(grid)

    @staticmethod
    def mask_code(code: str) -> str:
        """Masks entered code digits (e.g. '12' -> '* * _ _')."""
        masked = []
        for i in range(4):
            if i < len(code):
                masked.append("*")
            else:
                masked.append("_")
        return " ".join(masked)
