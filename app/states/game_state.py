"""In-memory (Redis-backed) domain models for a live, in-progress game.

These are intentionally separate from `app.models` (SQLAlchemy): those
model *archived, finished* games in Postgres, while these model the
*live* game while it's still being played — lobby, timer, votes.
"""

from __future__ import annotations

import enum
import time

from pydantic import BaseModel, Field

from app.models.enums import PlayerRole


class GameStatus(enum.StrEnum):
    """Lifecycle status of a live game stored in Redis."""

    LOBBY = "lobby"
    """Game created, waiting for players to join and the creator to start it."""

    RUNNING = "running"
    """Round in progress; players are discussing and the spy may guess."""

    VOTING = "voting"
    """Round time is up; players are voting on who they suspect."""

    AWAITING_FINAL_GUESS = "awaiting_final_guess"
    """The spy was voted out and now has one message to guess the word."""


class PlayerState(BaseModel):
    """A single player's live state within one game."""

    user_id: int
    display_name: str
    is_creator: bool = False
    role: PlayerRole | None = None
    joined_at: float = Field(default_factory=time.time)
    votes_received: int = 0
    eliminated: bool = False
    left_mid_game: bool = False


class GameSettings(BaseModel):
    """The tunable settings chosen from the pre-game settings panel."""

    spies_count: int
    round_seconds: int
    allow_two_spies: bool


class GameState(BaseModel):
    """Full snapshot of one chat's active game, as read from Redis."""

    chat_id: int
    creator_id: int
    creator_name: str
    status: GameStatus
    settings: GameSettings
    word: str | None = None
    created_at: float
    started_at: float | None = None
    ends_at: float | None = None
    lobby_message_id: int | None = None
    game_message_id: int | None = None
    voting_round: int = 1
    # When set, only these user_ids are valid vote targets (runoff).
    vote_candidate_ids: list[int] | None = None
    players: list[PlayerState] = Field(default_factory=list)

    @property
    def player_count(self) -> int:
        return len(self.players)

    def get_player(self, user_id: int) -> PlayerState | None:
        return next((p for p in self.players if p.user_id == user_id), None)

    @property
    def spies(self) -> list[PlayerState]:
        return [p for p in self.players if p.role == PlayerRole.SPY]

    @property
    def citizens(self) -> list[PlayerState]:
        return [p for p in self.players if p.role == PlayerRole.CITIZEN]
