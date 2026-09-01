"""HTML formatting helpers for building Telegram messages.

The bot's default parse mode is HTML (see `app.bot.bootstrap`), so all
message text built here uses HTML tags/entities.
"""

from __future__ import annotations

import html
import time
from typing import TYPE_CHECKING

from app.domain.game_state import GameState

if TYPE_CHECKING:
    from app.models.enums import GameEndReason, GameWinner


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


def build_game_message_text(game: GameState) -> str:
    """Render the in-progress game panel body (running phase)."""
    remaining = ""
    if game.ends_at is not None:
        secs = max(0, int(game.ends_at - time.time()))
        mins, secs = divmod(secs, 60)
        remaining = f"⏱ زمان باقی‌مانده: <b>{mins}:{secs:02d}</b>\n"

    lines = [
        "🎭 <b>بازی جاسوس شروع شد!</b>",
        "",
        remaining,
        "هر بازیکن نقش خودش را با دکمه‌ی زیر می‌بیند.",
        "شهروندان باید جاسوس را پیدا کنند؛ جاسوس باید کلمه را حدس بزند.",
        "",
        f"👥 <b>بازیکنان ({game.player_count} نفر):</b>",
    ]
    for i, p in enumerate(game.players, start=1):
        lines.append(f"{i}. {user_mention(p.user_id, p.display_name)}")
    return "\n".join(lines)


def build_voting_message_text(game: GameState) -> str:
    """Render the voting-panel body after the round timer expires."""
    lines = [
        "🗳 <b>زمان رای‌گیری</b>",
        "",
        "وقت بحث تمام شد. به کسی که فکر می‌کنید جاسوس است رای بدهید.",
        "",
        "👥 <b>بازیکنان فعال:</b>",
    ]
    active = [p for p in game.players if not p.eliminated and not p.left_mid_game]
    for i, p in enumerate(active, start=1):
        lines.append(f"{i}. {user_mention(p.user_id, p.display_name)}")
    return "\n".join(lines)


def role_reveal_text(*, is_spy: bool, word: str | None) -> str:
    """Private popup / alert text shown when a player taps «دیدن نقش من».

    Telegram alert popups are limited to ~200 characters, so keep this short.
    HTML is NOT rendered inside show_alert popups — plain text only.
    """
    if is_spy:
        return (
            "🕵️ شما جاسوس هستید!\n\n"
            "کلمه را نمی‌دانید. با دقت گوش دهید و سعی کنید "
            "کلمه را حدس بزنید بدون اینکه لو بروید."
        )
    return (
        f"👤 شما شهروند هستید.\n\n"
        f"کلمه مخفی: {word or '???'}\n\n"
        "با بقیه همکاری کنید تا جاسوس را پیدا کنید."
    )


def build_game_over_text(
    game: GameState,
    *,
    winner: GameWinner,
    reason: GameEndReason,
) -> str:
    """Public announcement when a game finishes."""
    from app.models.enums import GameEndReason, GameWinner

    spy_names = (
        ", ".join(user_mention(p.user_id, p.display_name) for p in game.spies) or "—"
    )
    word = html.escape(game.word or "???")

    if winner == GameWinner.SPY:
        if reason == GameEndReason.SPY_GUESSED_WORD:
            headline = "🕵️ <b>جاسوس(ها) برنده شدند!</b>"
            detail = "جاسوس کلمه را درست حدس زد."
        elif reason == GameEndReason.CITIZEN_VOTED_OUT:
            headline = "🕵️ <b>جاسوس(ها) برنده شدند!</b>"
            detail = "یک شهروند به‌اشتباه رای آورد و اخراج شد."
        elif reason == GameEndReason.SPY_VOTED_OUT_CORRECT_GUESS:
            headline = "🕵️ <b>جاسوس(ها) برنده شدند!</b>"
            detail = "جاسوس رای آورد ولی در حدس نهایی کلمه را درست گفت."
        else:
            headline = "🕵️ <b>جاسوس(ها) برنده شدند!</b>"
            detail = ""
    else:
        if reason == GameEndReason.SPY_VOTED_OUT_WRONG_GUESS:
            headline = "👥 <b>شهروندان برنده شدند!</b>"
            detail = "جاسوس رای آورد و نتوانست کلمه را حدس بزند."
        else:
            headline = "👥 <b>شهروندان برنده شدند!</b>"
            detail = ""

    lines = [
        headline,
        "",
        detail,
        f"🔤 کلمه: <b>{word}</b>",
        f"🕵️ جاسوس(ها): {spy_names}",
    ]
    return "\n".join(line for line in lines if line is not None)
