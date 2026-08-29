"""Repository for live game state: lobby, settings, timer, and votes.

Backed entirely by Redis. See `app.repositories.redis_keys` for the key
layout and `app.repositories.lua_scripts` for the atomic operations that
protect against concurrent access from multiple players/admins.
"""

from __future__ import annotations

import time

from redis.asyncio import Redis
from redis.commands.core import AsyncScript

from app.domain.game_state import GameSettings, GameState, GameStatus, PlayerState
from app.repositories import lua_scripts, redis_keys


class GameAlreadyExistsError(Exception):
    """Raised when trying to create a game in a chat that already has one."""


class GameNotFoundError(Exception):
    """Raised when an operation targets a chat with no active game."""


class NotInLobbyError(Exception):
    """Raised when a lobby-only operation is attempted outside the lobby phase."""


class AlreadyJoinedError(Exception):
    """Raised when a user who already joined tries to join again."""


class LobbyFullError(Exception):
    """Raised when the lobby has reached its configured max player count."""


class NotAParticipantError(Exception):
    """Raised when a non-participant tries to leave/vote in a game."""


class CreatorCannotLeaveError(Exception):
    """Raised when the game's creator tries to leave instead of deleting it."""


class NotAuthorizedError(Exception):
    """Raised when a user without permission tries to delete the game."""


class NotInVotingPhaseError(Exception):
    """Raised when a vote is cast outside the voting phase."""


class AlreadyVotedError(Exception):
    """Raised when a user tries to vote more than once."""


class GameStateRepository:
    """Async repository wrapping all Redis access for live game state."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._create_script: AsyncScript = redis.register_script(
            lua_scripts.CREATE_GAME
        )
        self._join_script: AsyncScript = redis.register_script(lua_scripts.JOIN_GAME)
        self._leave_script: AsyncScript = redis.register_script(
            lua_scripts.LEAVE_GAME
        )
        self._delete_script: AsyncScript = redis.register_script(
            lua_scripts.DELETE_GAME
        )
        self._vote_script: AsyncScript = redis.register_script(
            lua_scripts.RECORD_VOTE
        )

    # Creation / deletion

    async def create_game(
        self,
        chat_id: int,
        creator_id: int,
        creator_name: str,
        settings: GameSettings,
        ttl_seconds: int,
    ) -> None:
        """Atomically create a new lobby with the creator as its first player.

        Raises `GameAlreadyExistsError` if a game is already active in
        this chat (see `create_game_lobby_exists` test for the guarantee
        under concurrent calls).
        """
        now = time.time()
        fields = {
            "status": GameStatus.LOBBY.value,
            "creator_id": str(creator_id),
            "creator_name": creator_name,
            "spies_count": str(settings.spies_count),
            "round_seconds": str(settings.round_seconds),
            "allow_two_spies": "1" if settings.allow_two_spies else "0",
            "word": "",
            "created_at": repr(now),
            "started_at": "",
            "ends_at": "",
            "lobby_message_id": "",
            "game_message_id": "",
        }
        flat_args: list[str] = []
        for key, value in fields.items():
            flat_args.extend([key, value])

        creator_player = PlayerState(
            user_id=creator_id, display_name=creator_name, is_creator=True
        )
        flat_args.extend(
            [str(creator_id), creator_player.model_dump_json(), str(ttl_seconds)]
        )

        created = await self._create_script(
            keys=[
                redis_keys.meta_key(chat_id),
                redis_keys.players_key(chat_id),
                redis_keys.order_key(chat_id),
            ],
            args=flat_args,
        )
        if created == 0:
            raise GameAlreadyExistsError(chat_id)

    async def delete_game(
        self, chat_id: int, requester_id: int, requester_is_group_admin: bool
    ) -> None:
        """Atomically delete a game if the requester is allowed to."""
        result = await self._delete_script(
            keys=redis_keys.all_keys(chat_id),
            args=[str(requester_id), "1" if requester_is_group_admin else "0"],
        )
        if result == -1:
            raise GameNotFoundError(chat_id)
        if result == -2:
            raise NotAuthorizedError(chat_id)

    async def force_delete_game(self, chat_id: int) -> None:
        """Delete a game unconditionally (used by the lobby-timeout auto-cleanup)."""
        await self._redis.delete(*redis_keys.all_keys(chat_id))

    async def game_exists(self, chat_id: int) -> bool:
        return bool(await self._redis.exists(redis_keys.meta_key(chat_id)))

    # Lobby membership

    async def join_game(
        self,
        chat_id: int,
        user_id: int,
        display_name: str,
        max_players: int,
        ttl_seconds: int,
    ) -> None:
        """Atomically add a player to the lobby."""
        player = PlayerState(user_id=user_id, display_name=display_name)
        result = await self._join_script(
            keys=[
                redis_keys.meta_key(chat_id),
                redis_keys.players_key(chat_id),
                redis_keys.order_key(chat_id),
            ],
            args=[
                str(user_id),
                player.model_dump_json(),
                str(max_players),
                str(ttl_seconds),
            ],
        )
        if result == -1:
            raise NotInLobbyError(chat_id)
        if result == -2:
            raise AlreadyJoinedError(user_id)
        if result == -3:
            raise LobbyFullError(chat_id)

    async def leave_game(self, chat_id: int, user_id: int) -> None:
        """Atomically remove a player from the lobby (creator cannot leave)."""
        result = await self._leave_script(
            keys=[
                redis_keys.meta_key(chat_id),
                redis_keys.players_key(chat_id),
                redis_keys.order_key(chat_id),
            ],
            args=[str(user_id)],
        )
        if result == -1:
            raise NotInLobbyError(chat_id)
        if result == -2:
            raise NotAParticipantError(user_id)
        if result == -3:
            raise CreatorCannotLeaveError(user_id)

    # Voting

    async def record_vote(self, chat_id: int, voter_id: int, target_id: int) -> None:
        """Atomically record one player's vote during the voting phase."""
        result = await self._vote_script(
            keys=[redis_keys.meta_key(chat_id), redis_keys.votes_key(chat_id)],
            args=[str(voter_id), str(target_id)],
        )
        if result == -1:
            raise NotInVotingPhaseError(chat_id)
        if result == -2:
            raise AlreadyVotedError(voter_id)

    async def get_votes(self, chat_id: int) -> dict[int, int]:
        """Return {voter_id: target_id} for all votes cast so far."""
        raw = await self._redis.hgetall(redis_keys.votes_key(chat_id))
        return {int(voter): int(target) for voter, target in raw.items()}

    # Field-level updates (non-racy: single-writer contexts like the
    # settings panel, or the creator-only "start game" action)

    async def update_settings(self, chat_id: int, settings: GameSettings) -> None:
        await self._redis.hset(
            redis_keys.meta_key(chat_id),
            mapping={
                "spies_count": str(settings.spies_count),
                "round_seconds": str(settings.round_seconds),
                "allow_two_spies": "1" if settings.allow_two_spies else "0",
            },
        )

    async def start_game(self, chat_id: int, word: str, round_seconds: int) -> float:
        """Transition LOBBY -> RUNNING, assign the word, and set the deadline.

        Role assignment happens in the service layer (it needs randomness
        and business rules like the 2-spy threshold); this only persists
        the resulting roles via `set_player_roles`.
        """
        now = time.time()
        ends_at = now + round_seconds
        await self._redis.hset(
            redis_keys.meta_key(chat_id),
            mapping={
                "status": GameStatus.RUNNING.value,
                "word": word,
                "started_at": repr(now),
                "ends_at": repr(ends_at),
            },
        )
        return ends_at

    async def set_status(self, chat_id: int, status: GameStatus) -> None:
        await self._redis.hset(redis_keys.meta_key(chat_id), "status", status.value)

    async def set_message_id(
        self, chat_id: int, *, lobby_message_id: int | None = None, game_message_id: int | None = None
    ) -> None:
        mapping: dict[str, str] = {}
        if lobby_message_id is not None:
            mapping["lobby_message_id"] = str(lobby_message_id)
        if game_message_id is not None:
            mapping["game_message_id"] = str(game_message_id)
        if mapping:
            await self._redis.hset(redis_keys.meta_key(chat_id), mapping=mapping)

    async def set_player_roles(self, chat_id: int, roles: dict[int, PlayerState]) -> None:
        """Overwrite full player records after role assignment at game start."""
        mapping = {
            str(user_id): player.model_dump_json() for user_id, player in roles.items()
        }
        await self._redis.hset(redis_keys.players_key(chat_id), mapping=mapping)

    async def eliminate_player(self, chat_id: int, user_id: int) -> None:
        """Mark a player as voted-out (used when building the outcome message)."""
        players_key = redis_keys.players_key(chat_id)
        raw = await self._redis.hget(players_key, str(user_id))
        if raw is None:
            raise NotAParticipantError(user_id)
        player = PlayerState.model_validate_json(raw)
        player.eliminated = True
        await self._redis.hset(players_key, str(user_id), player.model_dump_json())

    async def mark_left_mid_game(self, chat_id: int, user_id: int) -> None:
        """Flag a player who left the group while a game was in progress."""
        players_key = redis_keys.players_key(chat_id)
        raw = await self._redis.hget(players_key, str(user_id))
        if raw is None:
            return
        player = PlayerState.model_validate_json(raw)
        player.left_mid_game = True
        await self._redis.hset(players_key, str(user_id), player.model_dump_json())

    # Reads

    async def get_game(self, chat_id: int) -> GameState | None:
        """Read the full current state of a chat's game, or None if none exists."""
        meta = await self._redis.hgetall(redis_keys.meta_key(chat_id))
        if not meta:
            return None

        order = await self._redis.lrange(redis_keys.order_key(chat_id), 0, -1)
        players_raw = await self._redis.hgetall(redis_keys.players_key(chat_id))
        players_by_id = {
            uid: PlayerState.model_validate_json(raw) for uid, raw in players_raw.items()
        }
        # Preserve join order; fall back to hash iteration for any stragglers
        # (shouldn't happen, but keeps reads defensive against partial writes).
        ordered_players = [players_by_id[uid] for uid in order if uid in players_by_id]

        def _optional_float(value: str) -> float | None:
            return float(value) if value else None

        def _optional_int(value: str) -> int | None:
            return int(value) if value else None

        return GameState(
            chat_id=chat_id,
            creator_id=int(meta["creator_id"]),
            creator_name=meta["creator_name"],
            status=GameStatus(meta["status"]),
            settings=GameSettings(
                spies_count=int(meta["spies_count"]),
                round_seconds=int(meta["round_seconds"]),
                allow_two_spies=meta.get("allow_two_spies") == "1",
            ),
            word=meta.get("word") or None,
            created_at=float(meta["created_at"]),
            started_at=_optional_float(meta.get("started_at", "")),
            ends_at=_optional_float(meta.get("ends_at", "")),
            lobby_message_id=_optional_int(meta.get("lobby_message_id", "")),
            game_message_id=_optional_int(meta.get("game_message_id", "")),
            players=ordered_players,
        )
