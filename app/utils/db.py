"""PostgreSQL / SQLAlchemy access — **disabled until next stage**.

Live game state uses Redis only. Persistent archival (finished games,
user stats, group records) is deferred; see ``TODO.md``.

Do not call these helpers from runtime paths until Postgres is re-enabled.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import NoReturn


def _disabled() -> NoReturn:
    raise RuntimeError(
        "PostgreSQL is disabled for now (next stage deferred). "
        "Live gameplay uses Redis only. See TODO.md."
    )


def get_engine() -> NoReturn:
    """Disabled until next stage (game archival)."""
    _disabled()


def get_session_factory() -> NoReturn:
    """Disabled until next stage (game archival)."""
    _disabled()


@asynccontextmanager
async def get_session() -> AsyncIterator[None]:
    """Disabled until next stage (game archival)."""
    _disabled()
    yield  # pragma: no cover


async def dispose_engine() -> None:
    """No-op while Postgres is disabled."""
    return None
