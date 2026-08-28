"""Persistent Telegram user profile and lifetime statistics."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.game_player import GamePlayer


class User(Base):
    """A Telegram user known to the bot.

    Created/updated the first time a user joins any game lobby.
    Statistics here are aggregated across all groups.
    """

    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(256))
    games_played: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    games_won: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    times_as_spy: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    times_spy_won: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    game_participations: Mapped[list[GamePlayer]] = relationship(
        back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User id={self.telegram_id} username={self.username!r}>"
