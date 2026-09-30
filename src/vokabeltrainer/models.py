"""Data structures shared across the vocabulary trainer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class FlashCard:
    """A single vocabulary flashcard.

    `card_id` is a stable id derived from the German word + category, so
    progress (ease factor, due date, ...) survives re-importing the same
    CSV file later (e.g. when you extend the demo dataset towards 3000
    words).
    """

    card_id: str
    german: str
    english: str
    category: str
    word_type: str = ""  # noun / verb / adjective / phrase / number / ...
    gender: str = ""  # der / die / das - only relevant for nouns
    verb_case: str = ""  # akkusativ / dativ - only if the verb *always* takes it
    example_de: str = ""
    example_en: str = ""

    # spaced-repetition state, updated by scheduler.review()
    ease_factor: float = 2.5
    interval_days: int = 0
    repetitions: int = 0
    due_date: date = field(default_factory=date.today)

    def grammar_hint(self) -> str:
        """Short hint shown next to the word, e.g. '(die)' or '(+Dativ)'."""
        if self.gender:
            return f"({self.gender})"
        if self.verb_case:
            return f"(+{self.verb_case.capitalize()})"
        return ""


# Keep the established name available to existing callers.
Card = FlashCard


@dataclass
class ReviewResult:
    """Outcome of reviewing one card, on the SM-2 0-5 quality scale."""

    card_id: str
    quality: int  # 0 = total blackout ... 5 = perfect recall
    reviewed_on: date = field(default_factory=date.today)
