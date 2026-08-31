"""Word bank: load words from a text file and pick one at random.

Format of ``data/words.txt``:
- One word per line (recommended for large lists), **or**
- Several words separated by commas on the same line.
- Blank lines and lines starting with ``#`` are ignored.

No per-group history is kept: repeats are allowed.  With a reasonably
large word list the chance of an immediate repeat is low, and Redis
stays free of unbounded used-word sets.
"""

from __future__ import annotations

import random

from app.config.settings import BASE_DIR
from app.utils.logging import get_logger

logger = get_logger(__name__)

WORDS_FILE = BASE_DIR / "data" / "words.txt"


def _load_words() -> list[str]:
    """Read and normalise the on-disk word list (cached after first call)."""
    if not hasattr(_load_words, "_cache"):
        if not WORDS_FILE.exists():
            raise FileNotFoundError(
                f"Word bank file not found: {WORDS_FILE}. "
                "Create data/words.txt with one word per line."
            )
        words: list[str] = []
        for line in WORDS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Also accept comma-separated entries on a single line.
            for part in line.split(","):
                part = part.strip()
                if part:
                    words.append(part)
        if not words:
            raise ValueError(f"Word bank file is empty: {WORDS_FILE}")
        _load_words._cache = words  # type: ignore[attr-defined]
        logger.info("word_bank_loaded", count=len(words), path=str(WORDS_FILE))
    return _load_words._cache  # type: ignore[attr-defined]


def reload_words() -> int:
    """Force-reload the word list from disk (useful after editing the file)."""
    if hasattr(_load_words, "_cache"):
        delattr(_load_words, "_cache")
    return len(_load_words())


def pick_word() -> str:
    """Pick a random word from the bank. Repeats are allowed."""
    words = _load_words()
    return random.choice(words)
