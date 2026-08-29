"""Typed callback_data schemas for every inline button in the bot.

Using aiogram's `CallbackData` factory (instead of hand-built strings)
gives us automatic, safe packing/parsing and keeps the 64-byte Telegram
callback_data limit from becoming a silent bug later.
"""

import enum

from aiogram.filters.callback_data import CallbackData


class SettingsAction(enum.StrEnum):
    """Actions available on the pre-game settings panel."""

    SET = "set"
    """Apply a new (round_seconds, allow_two_spies) combination and re-render."""

    CONFIRM = "confirm"
    """Finalize these settings and create the game lobby."""

    CANCEL = "cancel"
    """Abandon the settings panel without creating a game."""


class NewGameSettingsCallback(CallbackData, prefix="ngs"):
    """Callback for the pre-game settings panel (round time, two-spy toggle).

    Every button carries the *full* resulting state (not a delta), so
    rendering never depends on anything other than what's in the callback
    itself — no external state needed to redraw the panel.
    """

    creator_id: int
    round_seconds: int
    allow_two_spies: bool
    action: SettingsAction


class LobbyAction(enum.StrEnum):
    """Actions available on the lobby (pre-start) panel."""

    JOIN = "join"
    LEAVE = "leave"
    DELETE = "delete"
    RULES = "rules"
    START = "start"


class LobbyCallback(CallbackData, prefix="lobby"):
    """Callback for the lobby panel: join / leave / delete / rules / start."""

    chat_id: int
    action: LobbyAction


class GameAction(enum.StrEnum):
    """Actions available on the in-progress game panel."""

    SEE_ROLE = "see_role"


class GameCallback(CallbackData, prefix="game"):
    """Callback for the in-progress game panel (currently: see my role)."""

    chat_id: int
    action: GameAction


class VoteCallback(CallbackData, prefix="vote"):
    """Callback for casting a vote against a specific player."""

    chat_id: int
    target_user_id: int
