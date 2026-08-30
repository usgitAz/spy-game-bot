"""HTML formatting helpers for building Telegram messages.

The bot's default parse mode is HTML (see `app.bot.bootstrap`), so all
message text built here uses HTML tags/entities.
"""

import html

from app.domain.game_state import GameState


def user_mention(user_id: int, display_name: str) -> str:
    """Build a clickable, tag-style mention that works even without a username."""
    safe_name = html.escape(display_name)
    return f'<a href="tg://user?id={user_id}">{safe_name}</a>'


def build_lobby_message_text(game: GameState) -> str:
    """Render the lobby panel body: intro + live member list."""
    lines = [
        "🎭 <b>بازی جاسوس</b>",
        "",
        "بازی داره شروع میشه؛ اگر قصد دارید به بازی بپیوندید، روی دکمه‌ی "
        "«پیوستن به بازی» بزنید.",
        "حتما قبل از بازی، قوانین بازی رو از دکمه‌ی «قوانین بازی» مطالعه کنید.",
        "",
        f"👥 <b>اعضا ({game.player_count} نفر):</b>",
    ]
    if game.players:
        lines.extend(
            f"{i}. {user_mention(p.user_id, p.display_name)}"
            for i, p in enumerate(game.players, start=1)
        )
    else:
        lines.append("هنوز کسی نپیوسته.")
    return "\n".join(lines)
