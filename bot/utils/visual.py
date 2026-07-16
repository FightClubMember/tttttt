class Visual:
    BORDER = "━━━━━━━━━━━━━━━━━━━━"
    LINE = "────────────────────"
    
    @staticmethod
    def header(title: str, subtitle: str = None) -> str:
        """Returns a premium header layout."""
        layout = f"💎 <b>{title}</b>\n"
        if subtitle:
            layout += f"⚡ <i>{subtitle}</i>\n"
        layout += f"{Visual.BORDER}\n"
        return layout

    @staticmethod
    def footer() -> str:
        """Returns standard footer styling."""
        return f"\n{Visual.BORDER}"

    @staticmethod
    def progress_bar(current: int, total: int, length: int = 10) -> str:
        """Generates a modern visual status/progress bar."""
        if total <= 0:
            return "░" * length + " 0%"
        percent = current / total
        filled_len = int(round(length * percent))
        bar = "█" * filled_len + "░" * (length - filled_len)
        return f"[{bar}] {int(percent * 100)}%"

    @staticmethod
    def loading_phase(phase: int) -> str:
        """Generates dynamic animated text for loading states."""
        phases = {
            1: "⏳ <b>Connecting to server...</b>",
            2: "⚡ <b>Retrieving database logs...</b>",
            3: "🚀 <b>Rendering visual interface...</b>"
        }
        return f"{Visual.BORDER}\n{phases.get(phase, '⏳ loading...')}\n{Visual.BORDER}"
