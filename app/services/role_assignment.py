"""Role assignment at game start: pick spies and tag every player.

Business rules (from product requirements):
- Base spy count comes from game settings (usually 1).
- If ``allow_two_spies`` is on **and** the lobby has
  ``spy_threshold_players`` (default 7) or more players, the spy count
  is raised to 2.
- Spies are chosen uniformly at random among all participants.
- Everyone else is a citizen.
"""

from __future__ import annotations

import random

from app.config.settings import get_settings
from app.domain.game_state import GameSettings, PlayerState
from app.models.enums import PlayerRole


def resolve_spies_count(player_count: int, settings: GameSettings) -> int:
    """Apply the 7+ / two-spy rule and clamp to configured min/max."""
    app = get_settings()
    count = settings.spies_count
    if settings.allow_two_spies and player_count >= app.spy_threshold_players:
        count = max(count, 2)
    return max(app.min_spies, min(count, app.max_spies, player_count - 1))


def assign_roles(
    players: list[PlayerState], settings: GameSettings
) -> dict[int, PlayerState]:
    """Return a new mapping ``user_id -> PlayerState`` with roles filled in.

    The original player objects are **not** mutated; fresh copies with
    ``role`` set are returned so callers can persist them atomically.
    """
    if not players:
        raise ValueError("Cannot assign roles to an empty player list")

    spies_count = resolve_spies_count(len(players), settings)
    spy_ids = set(random.sample([p.user_id for p in players], k=spies_count))

    result: dict[int, PlayerState] = {}
    for p in players:
        updated = p.model_copy(
            update={
                "role": (PlayerRole.SPY if p.user_id in spy_ids else PlayerRole.CITIZEN)
            }
        )
        result[p.user_id] = updated
    return result
