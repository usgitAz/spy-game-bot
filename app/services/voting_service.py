"""Vote tallying, runoff on tie, and final resolution."""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass

from aiogram import Bot

from app.config.settings import get_settings
from app.domain.game_state import GameState, GameStatus, PlayerState
from app.keyboards import build_voting_keyboard
from app.models.enums import GameEndReason, GameWinner, PlayerRole
from app.repositories.game_state_repository import GameStateRepository
from app.services.final_guess_service import start_final_guess_window
from app.services.game_end_service import end_game
from app.utils.formatting import (
    build_vote_results_text,
    build_voting_message_text,
    user_mention,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class VoteTally:
    """votes_for covers every candidate; top_ids are those with the max count."""

    votes_for: dict[int, int]
    top_ids: list[int]
    max_votes: int


def _candidate_pool(game: GameState) -> list[PlayerState]:
    """Players who may be voted for this round (runoff narrows the list)."""
    active = [p for p in game.players if not p.eliminated and not p.left_mid_game]
    if game.vote_candidate_ids is None:
        return active
    allowed = set(game.vote_candidate_ids)
    return [p for p in active if p.user_id in allowed]


def tally_votes(candidates: list[PlayerState], votes: dict[int, int]) -> VoteTally:
    """Count votes only for the current candidate pool."""
    candidate_ids = {p.user_id for p in candidates}
    counts: Counter[int] = Counter()
    for _voter, target in votes.items():
        if target in candidate_ids:
            counts[target] += 1

    votes_for = {p.user_id: counts.get(p.user_id, 0) for p in candidates}

    if not candidates:
        return VoteTally(votes_for={}, top_ids=[], max_votes=0)

    max_votes = max(votes_for.values()) if votes_for else 0
    top_ids = [uid for uid, n in votes_for.items() if n == max_votes]
    return VoteTally(votes_for=votes_for, top_ids=top_ids, max_votes=max_votes)


async def resolve_voting(
    bot: Bot,
    repo: GameStateRepository,
    chat_id: int,
) -> None:
    """Close the current voting round.

    - Unique top → eliminate and finish (or open final-guess for a spy).
    - Tie on round 1 → start a runoff among the tied players only.
    - Tie on round 2 → declare a draw (no winner).
    """
    game = await repo.get_game(chat_id)
    if game is None or game.status != GameStatus.VOTING:
        return

    # Prevent double-resolve (all-voted + timer racing).
    await repo.set_status(chat_id, GameStatus.AWAITING_FINAL_GUESS)

    candidates = _candidate_pool(game)
    votes = await repo.get_votes(chat_id)
    tally = tally_votes(candidates, votes)

    # Remove current voting panel.
    if game.game_message_id is not None:
        try:
            await bot.delete_message(chat_id, game.game_message_id)
        except Exception:  # noqa: BLE001
            pass

    results_text = build_vote_results_text(game, tally.votes_for)
    try:
        await bot.send_message(chat_id, results_text)
    except Exception:  # noqa: BLE001
        logger.exception("vote_results_announce_failed", chat_id=chat_id)

    # --- Tie handling ---
    if len(tally.top_ids) != 1:
        if game.voting_round <= 1:
            await _start_runoff(bot, repo, game, tally.top_ids)
            return

        # Second round still tied → draw.
        try:
            await bot.send_message(
                chat_id,
                "⚖️ رای‌ها در دور دوم هم مساوی ماند.\n"
                "بازی <b>مساوی</b> اعلام می‌شود — برنده‌ای نیست.",
            )
        except Exception:  # noqa: BLE001
            pass
        # Re-read after status flip for a consistent snapshot.
        game = await repo.get_game(chat_id) or game
        await end_game(
            bot,
            repo,
            game,
            winner=GameWinner.DRAW,
            reason=GameEndReason.VOTE_TIE,
            announce=True,
        )
        return

    eliminated_id = tally.top_ids[0]
    await _apply_elimination(bot, repo, chat_id, eliminated_id)


async def _start_runoff(
    bot: Bot,
    repo: GameStateRepository,
    game: GameState,
    tied_ids: list[int],
) -> None:
    """Open a second voting round restricted to the tied players."""
    chat_id = game.chat_id
    tied_players = [p for p in game.players if p.user_id in set(tied_ids)]
    names = ", ".join(user_mention(p.user_id, p.display_name) for p in tied_players)

    await repo.set_vote_runoff(chat_id, round_number=2, candidate_ids=tied_ids)
    voting_ends = time.time() + get_settings().voting_timeout_seconds
    await repo.set_voting_deadline(chat_id, voting_ends)

    try:
        await bot.send_message(
            chat_id,
            "⚖️ رای‌ها مساوی شد بین: "
            f"{names}\n\n"
            "دور دوم رای‌گیری فقط بین همین نفرات شروع می‌شود. "
            "مهلت: <b>۱ دقیقه</b>.",
        )
    except Exception:  # noqa: BLE001
        pass

    game = await repo.get_game(chat_id)
    assert game is not None
    text = build_voting_message_text(game, runoff=True)
    keyboard = build_voting_keyboard(chat_id, tied_players)
    sent = await bot.send_message(chat_id, text, reply_markup=keyboard)
    await repo.set_message_id(chat_id, game_message_id=sent.message_id)

    from app.services.voting_timeout_service import start_voting_timeout

    start_voting_timeout(bot, repo, chat_id)
    logger.info(
        "vote_runoff_started",
        chat_id=chat_id,
        candidates=tied_ids,
    )


async def _apply_elimination(
    bot: Bot,
    repo: GameStateRepository,
    chat_id: int,
    eliminated_id: int,
) -> None:
    game = await repo.get_game(chat_id)
    if game is None:
        return

    eliminated = game.get_player(eliminated_id)
    if eliminated is None:
        return

    await repo.eliminate_player(chat_id, eliminated_id)
    game = await repo.get_game(chat_id)
    assert game is not None
    eliminated = game.get_player(eliminated_id)
    assert eliminated is not None

    elim_mention = user_mention(eliminated.user_id, eliminated.display_name)

    if eliminated.role != PlayerRole.SPY:
        try:
            await bot.send_message(
                chat_id, f"❌ {elim_mention} با بیشترین رای اخراج شد، اما شهروند بود."
            )
        except Exception:  # noqa: BLE001
            pass
        await end_game(
            bot,
            repo,
            game,
            winner=GameWinner.SPY,
            reason=GameEndReason.CITIZEN_VOTED_OUT,
            announce=True,
        )
        return

    # Spy voted out → 30s final-guess window.
    await repo.set_status(chat_id, GameStatus.AWAITING_FINAL_GUESS)
    try:
        await bot.send_message(
            chat_id,
            f"🕵️ {elim_mention} با بیشترین رای اخراج شد و <b>جاسوس</b> بود!\n\n"
            "۳۰ ثانیه فرصت داری عین کلمه را در چت بفرستی. "
            "اگر درست بگویی می‌بری؛ وگرنه شهروندان برنده می‌شوند.",
        )
    except Exception:  # noqa: BLE001
        pass

    start_final_guess_window(bot, repo, chat_id, eliminated.user_id)
    logger.info(
        "spy_voted_out_final_guess",
        chat_id=chat_id,
        spy_id=eliminated.user_id,
    )
