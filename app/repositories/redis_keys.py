"""Centralized Redis key builders for live game state.

Keeping all key formats in one place avoids typos and makes it trivial
to change the naming scheme later without hunting through the codebase.
"""

_PREFIX = "spy:game"


def meta_key(chat_id: int) -> str:
    """Hash: game metadata (status, settings, timing, panel message ids)."""
    return f"{_PREFIX}:{chat_id}:meta"


def players_key(chat_id: int) -> str:
    """Hash: user_id -> JSON-encoded player state."""
    return f"{_PREFIX}:{chat_id}:players"


def order_key(chat_id: int) -> str:
    """List: user_ids in join order."""
    return f"{_PREFIX}:{chat_id}:order"


def votes_key(chat_id: int) -> str:
    """Hash: voter_id -> target_id."""
    return f"{_PREFIX}:{chat_id}:votes"


def all_keys(chat_id: int) -> list[str]:
    """All Redis keys belonging to one chat's active game (for atomic cleanup)."""
    return [
        meta_key(chat_id),
        players_key(chat_id),
        order_key(chat_id),
        votes_key(chat_id),
    ]
