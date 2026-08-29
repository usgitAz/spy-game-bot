"""Keyboard for the lobby panel: join / leave / delete / rules / start."""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.callback_data import LobbyAction, LobbyCallback


def build_lobby_keyboard(chat_id: int, *, show_start: bool) -> InlineKeyboardMarkup:
    """Render the lobby panel.

    Args:
        chat_id: The group chat this lobby belongs to.
        show_start: Whether to show the "شروع بازی" button. The handler
            decides this (e.g. only once the minimum player count is met),
            keeping that business rule out of the keyboard layer.

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

    if show_start:
        builder.button(
            text="🚀 شروع بازی",
            callback_data=LobbyCallback(chat_id=chat_id, action=LobbyAction.START),
        )
        builder.adjust(2, 2, 1)
    else:
        builder.adjust(2, 2)

    return builder.as_markup()
