"""Handle a participant leaving the Telegram group while a game is live.

Rules (product):
- LOBBY: non-creator removed from the roster; creator → whole game deleted.
- RUNNING / VOTING: mark ``left_mid_game``; if the last active spy is gone →
  citizens win; if active players drop below ``min_players`` → draw.
- AWAITING_FINAL_GUESS: if the eliminated spy leaves → citizens win.
"""

from __future__ import annotations

from aiogram import Bot

from app.config.settings import get_settings
from app.domain.game_state import GameState, GameStatus
from app.keyboards import build_lobby_keyboard, build_voting_keyboard
from app.models.enums import GameEndReason, GameWinner, PlayerRole
from app.repositories.game_state_repository import (
    CreatorCannotLeaveError,
    GameStateRepository,
    NotAParticipantError,
    NotInLobbyError,
)
from app.services.game_end_service import end_game
from app.utils.formatting import (
    build_lobby_message_text,
    build_voting_message_text,
    force_rtl,
    user_mention,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _active_players(game: GameState) -> list:
    return [p for p in game.players if not p.eliminated and not p.left_mid_game]


def _active_spies(game: GameState) -> list:
    return [p for p in _active_players(game) if p.role == PlayerRole.SPY]


async def handle_member_left(
    bot: Bot,
    repo: GameStateRepository,
    *,
    chat_id: int,
    user_id: int,
    display_name: str,
) -> None:
    """React to a user leaving/being kicked from ``chat_id``."""
    game = await repo.get_game(chat_id)
    if game is None:
        return

    player = game.get_player(user_id)
    if player is None:
        return

    if game.status == GameStatus.LOBBY:
        await _handle_lobby_leave(bot, repo, game, user_id, display_name)
        return

    if game.status in (GameStatus.RUNNING, GameStatus.VOTING):
        await _handle_in_game_leave(bot, repo, game, user_id, display_name)
        return

    if game.status == GameStatus.AWAITING_FINAL_GUESS:
        await _handle_final_guess_leave(bot, repo, game, user_id, display_name)
        return


async def handle_bot_removed(
    bot: Bot,
    repo: GameStateRepository,
    *,
    chat_id: int,
) -> None:
    """Bot was kicked/removed — drop any live state for this chat silently."""
    existed = await repo.game_exists(chat_id)
    if not existed:
        return
    await repo.force_delete_game(chat_id)
    logger.info("bot_removed_game_cleared", chat_id=chat_id)


async def _handle_lobby_leave(
    bot: Bot,
    repo: GameStateRepository,
    game: GameState,
    user_id: int,
    display_name: str,
) -> None:
    chat_id = game.chat_id
    mention = user_mention(user_id, display_name)

    if user_id == game.creator_id:
        for msg_id in (game.lobby_message_id, game.game_message_id):
            if msg_id is None:
                continue
            try:
                await bot.delete_message(chat_id, msg_id)
            except Exception:  # noqa: BLE001
                pass
        await repo.force_delete_game(chat_id)
        try:
            await bot.send_message(
                chat_id,
                force_rtl(f"🗑 {mention} (سازنده بازی) از گروه خارج شد؛ بازی حذف شد."),
            )
        except Exception:  # noqa: BLE001
            pass
        logger.info("lobby_creator_left", chat_id=chat_id, user_id=user_id)
        return

    try:
        await repo.leave_game(chat_id, user_id)
    except (NotInLobbyError, NotAParticipantError, CreatorCannotLeaveError):
        return

    game = await repo.get_game(chat_id)
    if game is None:
        return

    try:
        await bot.send_message(
            chat_id,
            force_rtl(f"👋 {mention} از گروه خارج شد و از لابی حذف شد."),
        )
    except Exception:  # noqa: BLE001
        pass

    if game.lobby_message_id is not None:
        try:
            # Re-render lobby list on the existing panel if we can find it —
            # safest is send is already done; edit by fetching is hard without
            # a Message object. Skip panel edit if we only have an id unless
            # we use bot.edit_message_text.
            await bot.edit_message_text(
                build_lobby_message_text(game),
                chat_id=chat_id,
                message_id=game.lobby_message_id,
                reply_markup=build_lobby_keyboard(chat_id),
            )
        except Exception:  # noqa: BLE001
            pass

    logger.info("lobby_player_left", chat_id=chat_id, user_id=user_id)


async def _handle_in_game_leave(
    bot: Bot,
    repo: GameStateRepository,
    game: GameState,
    user_id: int,
    display_name: str,
) -> None:
    chat_id = game.chat_id
    mention = user_mention(user_id, display_name)
    was_spy = game.get_player(user_id) is not None and (
        game.get_player(user_id).role == PlayerRole.SPY  # type: ignore[union-attr]
    )

    await repo.mark_left_mid_game(chat_id, user_id)
    game = await repo.get_game(chat_id)
    if game is None:
        return

    try:
        await bot.send_message(
            chat_id,
            force_rtl(f"🚪 {mention} از گروه خارج شد و از بازی کنار گذاشته شد."),
        )
    except Exception:  # noqa: BLE001
        pass

    active = _active_players(game)
    min_players = get_settings().min_players

    if len(active) < min_players:
        await end_game(
            bot,
            repo,
            game,
            winner=GameWinner.DRAW,
            reason=GameEndReason.TOO_FEW_PLAYERS,
            announce=True,
        )
        logger.info(
            "game_aborted_too_few_after_leave",
            chat_id=chat_id,
            user_id=user_id,
            active=len(active),
        )
        return

    if was_spy and not _active_spies(game):
        await end_game(
            bot,
            repo,
            game,
            winner=GameWinner.CITIZENS,
            reason=GameEndReason.SPY_LEFT_GROUP,
            announce=True,
        )
        logger.info(
            "last_spy_left_citizens_win",
            chat_id=chat_id,
            user_id=user_id,
        )
        return

    # Still playable — if voting, refresh the panel without the leaver.
    if game.status == GameStatus.VOTING and game.game_message_id is not None:
        try:
            await bot.edit_message_text(
                build_voting_message_text(game),
                chat_id=chat_id,
                message_id=game.game_message_id,
                reply_markup=build_voting_keyboard(chat_id, active),
            )
        except Exception:  # noqa: BLE001
            pass

    logger.info(
        "player_left_mid_game_continue",
        chat_id=chat_id,
        user_id=user_id,
        was_spy=was_spy,
        active=len(active),
    )


async def _handle_final_guess_leave(
    bot: Bot,
    repo: GameStateRepository,
    game: GameState,
    user_id: int,
    display_name: str,
) -> None:
    player = game.get_player(user_id)
    if player is None:
        return

    mention = user_mention(user_id, display_name)

    # The voted-out spy must send the final guess; if they leave, citizens win.
    if player.role == PlayerRole.SPY and player.eliminated:
        try:
            await bot.send_message(
                chat_id=game.chat_id,
                text=force_rtl(
                    f"🚪 {mention} (جاسوس) از گروه خارج شد و فرصت حدس را از دست داد."
                ),
            )
        except Exception:  # noqa: BLE001
            pass
        await end_game(
            bot,
            repo,
            game,
            winner=GameWinner.CITIZENS,
            reason=GameEndReason.SPY_VOTED_OUT_WRONG_GUESS,
            announce=True,
        )
        logger.info(
            "final_guess_spy_left",
            chat_id=game.chat_id,
            user_id=user_id,
        )
        return

    await repo.mark_left_mid_game(game.chat_id, user_id)
    try:
        await bot.send_message(
            game.chat_id,
            force_rtl(f"🚪 {mention} از گروه خارج شد."),
        )
    except Exception:  # noqa: BLE001
        pass
