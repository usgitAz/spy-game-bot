"""Keyboard for the lobby panel: join / leave / delete / rules / start."""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.callback_data import LobbyAction, LobbyCallback


def build_lobby_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Render the lobby panel.

    The "شروع بازی" button is always shown (better UX than hiding it);
    if there aren't enough players yet, the handler responds to the tap
    with an alert instead of silently doing nothing.
    """
    builder = InlineKeyboardBuilder()

    builder.button(
        text="➕ پیوستن به بازی",
        callback_data=LobbyCallback(chat_id=chat_id, action=LobbyAction.JOIN),
    )
    builder.button(
        text="➖ خروج از بازی",
        callback_data=LobbyCallback(chat_id=chat_id, action=LobbyAction.LEAVE),
    )
    builder.button(
        text="🗑 حذف بازی",
        callback_data=LobbyCallback(chat_id=chat_id, action=LobbyAction.DELETE),
    )
    builder.button(
        text="📜 قوانین بازی",
        callback_data=LobbyCallback(chat_id=chat_id, action=LobbyAction.RULES),
    )
    builder.button(
        text="🚀 شروع بازی",
        callback_data=LobbyCallback(chat_id=chat_id, action=LobbyAction.START),
    )
    builder.adjust(2, 2, 1)

    return builder.as_markup()
