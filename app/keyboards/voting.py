"""Keyboard for the voting panel: one button per active player."""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.domain.game_state import PlayerState
from app.keyboards.callback_data import VoteCallback


def build_voting_keyboard(
    chat_id: int, players: list[PlayerState]
) -> InlineKeyboardMarkup:
    """Render one button per player who can be voted for.

    Every player (including the spy) can vote, and every player is a
    valid target -- this matches the rule that voting is open to all.
    """
    builder = InlineKeyboardBuilder()
    for player in players:
        builder.button(
            text=player.display_name,
            callback_data=VoteCallback(chat_id=chat_id, target_user_id=player.user_id),
        )
    builder.adjust(2)
    return builder.as_markup()
