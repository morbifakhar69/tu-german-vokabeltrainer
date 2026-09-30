"""Tests for flashcard and review result model defaults."""

from datetime import date

import pytest

from vokabeltrainer import FlashCard, ReviewResult


def make_card(**overrides) -> FlashCard:
    values = {
        "card_id": "test-card",
        "german": "lernen",
        "english": "to learn",
        "category": "verbs",
    }
    values.update(overrides)
    return FlashCard(**values)


def test_flashcard_has_beginner_friendly_scheduling_defaults():
    card = make_card()

    assert card.ease_factor == 2.5
    assert card.interval_days == 0
    assert card.repetitions == 0
    assert card.due_date == date.today()


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"gender": "die"}, "(die)"),
        ({"verb_case": "dativ"}, "(+Dativ)"),
        ({"gender": "der", "verb_case": "akkusativ"}, "(der)"),
        ({}, ""),
    ],
)
def test_flashcard_grammar_hint(overrides, expected):
    assert make_card(**overrides).grammar_hint() == expected


def test_review_result_accepts_an_explicit_review_date():
    reviewed_on = date(2026, 9, 30)

    result = ReviewResult(card_id="test-card", quality=5, reviewed_on=reviewed_on)

    assert result.card_id == "test-card"
    assert result.quality == 5
    assert result.reviewed_on == reviewed_on
