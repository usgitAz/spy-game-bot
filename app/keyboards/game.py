"""Keyboard for the in-progress game panel: see my role."""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.callback_data import GameAction, GameCallback


def build_game_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Render the in-progress game panel (currently just 'see my role')."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🎭 دیدن نقش من",
        callback_data=GameCallback(chat_id=chat_id, action=GameAction.SEE_ROLE),
    )
    return builder.as_markup()
