"""Mid-round spy word-guess logic.

A spy wins instantly by sending a chat message whose *entire* text is
exactly the secret word (after stripping leading/trailing whitespace).
"""

from __future__ import annotations

from app.domain.game_state import GameState, GameStatus
from app.models.enums import PlayerRole


def normalize_guess(text: str) -> str:
    """Strip outer whitespace only — no lowercasing (Persian has no case)."""
    return text.strip()


def is_exact_word_guess(message_text: str, word: str) -> bool:
    """True only when the whole message equals the secret word."""
    if not word:
        return False
    return normalize_guess(message_text) == normalize_guess(word)


def player_may_guess(game: GameState, user_id: int) -> bool:
    """Spy participants may guess only while the round is RUNNING."""
    if game.status != GameStatus.RUNNING:
        return False
    if not game.word:
        return False
    player = game.get_player(user_id)
    if player is None:
        return False
    if player.eliminated or player.left_mid_game:
        return False
    return player.role == PlayerRole.SPY
