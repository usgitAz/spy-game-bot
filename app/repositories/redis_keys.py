"""Centralized Redis key builders for live game state.

Keeping all key formats in one place avoids typos and makes it trivial
to change the naming scheme later without hunting through the codebase.
"""

_PREFIX = "spy:game"

# Voting has at most two rounds (initial + one runoff).
_MAX_VOTING_ROUNDS = 2


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


def resolve_lock_key(chat_id: int, voting_round: int = 1) -> str:
    """NX lock for one voting-round resolution (timer vs all-voted).

    Scoped by ``voting_round`` so a runoff is not blocked by the lock
    from round 1 (which may still have up to ~120s of TTL left).
    """
    return f"{_PREFIX}:{chat_id}:resolve_lock:{int(voting_round)}"


def all_keys(chat_id: int) -> list[str]:
    """All Redis keys belonging to one chat's active game (for atomic cleanup)."""
    keys = [
        meta_key(chat_id),
        players_key(chat_id),
        order_key(chat_id),
        votes_key(chat_id),
    ]
    # Include every possible resolve-lock round so cleanup never leaves stragglers.
    for round_no in range(1, _MAX_VOTING_ROUNDS + 1):
        keys.append(resolve_lock_key(chat_id, round_no))
    # Legacy unscoped key from older builds (safe no-op if missing).
    keys.append(f"{_PREFIX}:{chat_id}:resolve_lock")
    return keys
