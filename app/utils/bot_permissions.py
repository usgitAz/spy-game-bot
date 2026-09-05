"""Helpers for checking the bot's membership / admin rights in a chat."""

from __future__ import annotations

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner

from app.utils.logging import get_logger

logger = get_logger(__name__)

_ADMIN_STATUSES = {
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.CREATOR,
    "administrator",
    "creator",
}

# Shown when the bot is used in a group where it is not an admin.
BOT_NOT_ADMIN_TEXT = (
    "⚠️ برای کار کردن این ربات باید آن را <b>ادمین گروه</b> کنید.\n\n"
    "حداقل دسترسی لازم: فقط وضعیت ادمین "
    "(برای دیدن خروج اعضا و مدیریت پیام‌های بازی).\n\n"
    "بعد از ادمین کردن، دوباره دستور را بزنید."
)


async def bot_is_group_admin(bot: Bot, chat_id: int) -> bool:
    """Return True if the bot is administrator (or creator) in ``chat_id``."""
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id, me.id)
    except Exception:
        logger.exception("bot_admin_check_failed", chat_id=chat_id)
        # Fail closed: treat as not-admin so we do not run game logic blindly.
        return False

    status = member.status
    if status not in _ADMIN_STATUSES:
        return False

    # Owner is always fine. Administrator is fine even without extra flags —
    # Telegram only delivers chat_member updates to admin bots.
    if isinstance(member, (ChatMemberOwner, ChatMemberAdministrator)):
        return True
    # status string path (older/mocked objects)
    return True
