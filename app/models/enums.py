"""Shared enum types used across the persistence layer."""

import enum


class PlayerRole(enum.StrEnum):
    """Role assigned to a player for a single finished game."""

    CITIZEN = "citizen"
    SPY = "spy"


class GameWinner(enum.StrEnum):
    """Which side won a finished game."""

    CITIZENS = "citizens"
    SPY = "spy"
    DRAW = "draw"
    """Vote runoff stayed tied — no winner / aborted with too few players."""


class GameEndReason(enum.StrEnum):
    """How a finished game concluded — kept for stats/analytics."""

    SPY_GUESSED_WORD = "spy_guessed_word"
    """The spy sent the correct word mid-game and won instantly."""
    SPY_VOTED_OUT_WRONG_GUESS = "spy_voted_out_wrong_guess"
    """The spy was voted out and failed to guess the word."""
    SPY_VOTED_OUT_CORRECT_GUESS = "spy_voted_out_correct_guess"
    """The spy was voted out but still guessed the word correctly and won."""
    CITIZEN_VOTED_OUT = "citizen_voted_out"
    """A citizen was voted out instead of the spy; the spy wins."""
    VOTE_TIE = "vote_tie"
    """Second-round vote stayed tied — game declared a draw."""
    SPY_LEFT_GROUP = "spy_left_group"
    """The last active spy left/was kicked mid-game; citizens win."""
    TOO_FEW_PLAYERS = "too_few_players"
    """Active players dropped below the minimum; game declared a draw."""
    CANCELLED = "cancelled"
    """The game was deleted/aborted before completion (e.g. lobby timeout)."""
