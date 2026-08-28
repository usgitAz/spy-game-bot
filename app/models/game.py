"""Persistent record of a single game, written when the game ends.

Note: live game state (lobby membership, active timer, in-progress votes)
lives in Redis, not here. Rows in this table are archival — created once
a game concludes (win, loss, or cancellation) so history/stats survive.
"""

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
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import GameEndReason, GameWinner

if TYPE_CHECKING:
    from app.models.game_player import GamePlayer
    from app.models.group import Group


class Game(Base):
    """A single game round played in a group, kept for history/stats."""

    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("groups.chat_id", ondelete="CASCADE"), index=True
    )
    creator_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id", ondelete="SET NULL"), nullable=True
    )
    word: Mapped[str] = mapped_column(String(128))
    spies_count: Mapped[int] = mapped_column(SmallInteger)
    round_seconds: Mapped[int] = mapped_column(Integer)
    allow_two_spies: Mapped[bool] = mapped_column(Boolean, default=False)
    winner: Mapped[GameWinner | None] = mapped_column(
        Enum(
            GameWinner,
            name="game_winner",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=True,
    )
    end_reason: Mapped[GameEndReason | None] = mapped_column(
        Enum(
            GameEndReason,
            name="game_end_reason",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    group: Mapped[Group] = relationship(back_populates="games")
    players: Mapped[list[GamePlayer]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Game id={self.id} chat_id={self.chat_id} winner={self.winner}>"
