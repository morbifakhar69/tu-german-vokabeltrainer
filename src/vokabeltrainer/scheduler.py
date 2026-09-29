"""A slightly simplified version of the SM-2 spaced-repetition algorithm.

Background: https://en.wikipedia.org/wiki/SuperMemo#Description_of_SM-2_algorithm

I left out some of the finer SuperMemo details (matrix of interoptimal
factors, etc.) since this is meant to be understandable for a course
project, not a full SuperMemo re-implementation.
"""

from __future__ import annotations

from datetime import date, timedelta

from vokabeltrainer.models import Card

MIN_EASE_FACTOR = 1.3


def review(card: Card, quality: int, today: date | None = None) -> Card:
    """Update a card's scheduling state after it has been reviewed.

    `quality` follows the original SM-2 0-5 scale:
        0-2 -> you didn't really remember it, reset the streak
        3-5 -> correct recall, interval grows (5 being "too easy")
    """
    if not 0 <= quality <= 5:
        raise ValueError("quality must be between 0 and 5")

    today = today or date.today()

    if quality < 3:
        card.repetitions = 0
        card.interval_days = 1
    else:
        if card.repetitions == 0:
            card.interval_days = 1
        elif card.repetitions == 1:
            card.interval_days = 6
        else:
            card.interval_days = round(card.interval_days * card.ease_factor)
        card.repetitions += 1

    # ease factor update, straight from the SM-2 paper
    card.ease_factor += 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    card.ease_factor = max(MIN_EASE_FACTOR, card.ease_factor)

    card.due_date = today + timedelta(days=card.interval_days)
    return card


def is_due(card: Card, today: date | None = None) -> bool:
    """Whether a card should be reviewed today (or is overdue)."""
    today = today or date.today()
    return card.due_date <= today


def due_cards(cards: list[Card], today: date | None = None) -> list[Card]:
    today = today or date.today()
    return [c for c in cards if is_due(c, today)]
