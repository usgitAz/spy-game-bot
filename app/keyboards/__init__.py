"""Reusable inline keyboards and their typed callback_data schemas."""

from app.keyboards.callback_data import (
    GameAction,
    GameCallback,
    LobbyAction,
    LobbyCallback,
    NewGameSettingsCallback,
    SettingsAction,
    VoteCallback,
)
from app.keyboards.game import build_game_keyboard
from app.keyboards.lobby import build_lobby_keyboard
from app.keyboards.new_game_settings import build_settings_keyboard
from app.keyboards.voting import build_voting_keyboard

__all__ = [
    "GameAction",
    "GameCallback",
    "LobbyAction",
    "LobbyCallback",
    "NewGameSettingsCallback",
    "SettingsAction",
    "VoteCallback",
    "build_game_keyboard",
    "build_lobby_keyboard",
    "build_settings_keyboard",
    "build_voting_keyboard",
]
