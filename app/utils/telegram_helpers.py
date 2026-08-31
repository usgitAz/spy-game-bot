"""Small helpers for safely interacting with the Telegram Bot API."""

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message


async def safe_edit_text(
    message: Message, text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> None:
    """Edit a message's text.

    silently ignoring the harmless case where thenew content is byte-for-byte identical to the old one.
    Telegram raises `TelegramBadRequest: message is not modified` in that
    case; it's not a real error, just Telegram refusing a no-op edit, and
    can legitimately happen here (e.g. two rapid callback presses).
    """
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise
