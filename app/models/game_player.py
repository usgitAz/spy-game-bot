"""Persistent record of a single player's participation in one game."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import PlayerRole

if TYPE_CHECKING:
    from app.models.game import Game
    from app.models.user import User


class GamePlayer(Base):
    """A player's role and outcome within a single archived game."""

    __tablename__ = "game_players"
    __table_args__ = (
        UniqueConstraint("game_id", "user_id", name="uq_game_players_game_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), index=True
    )
    # Denormalized snapshot of the display name at play time, so history
    # still reads correctly even if the user later changes their name.
    display_name: Mapped[str] = mapped_column(String(256))
    role: Mapped[PlayerRole] = mapped_column(
        Enum(PlayerRole, name="player_role", native_enum=True)
    )
    is_creator: Mapped[bool] = mapped_column(Boolean, default=False)
    votes_received: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    was_eliminated: Mapped[bool] = mapped_column(Boolean, default=False)
    # Set when a player leaves the group mid-game (sudden-exit handling).
    left_mid_game: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    game: Mapped[Game] = relationship(back_populates="players")
    user: Mapped[User] = relationship(back_populates="game_participations")

    def __repr__(self) -> str:
        return f"<GamePlayer game_id={self.game_id} user_id={self.user_id} role={self.role}>"