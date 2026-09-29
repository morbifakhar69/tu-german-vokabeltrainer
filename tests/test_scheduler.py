"""Tests for the SM-2 style scheduler."""

from datetime import date

from vokabeltrainer.models import Card
from vokabeltrainer.scheduler import due_cards, is_due, review


def make_card(**overrides) -> Card:
    defaults = dict(card_id="abc123", german="Hund", english="dog", category="animals")
    defaults.update(overrides)
    return Card(**defaults)


def test_good_recall_grows_interval():
    card = make_card()
    today = date(2026, 1, 1)

    review(card, quality=4, today=today)
    assert card.repetitions == 1
    assert card.interval_days == 1

    review(card, quality=4, today=today)
    assert card.repetitions == 2
    assert card.interval_days == 6

    review(card, quality=4, today=today)
    assert card.repetitions == 3
    # third+ review: interval = round(previous_interval * ease_factor)
    assert card.interval_days == round(6 * card.ease_factor)


def test_forgetting_resets_streak():
    card = make_card()
    today = date(2026, 1, 1)
    review(card, quality=5, today=today)
    review(card, quality=5, today=today)
    assert card.repetitions == 2

    review(card, quality=1, today=today)  # forgot it
    assert card.repetitions == 0
    assert card.interval_days == 1


def test_ease_factor_has_a_floor():
    card = make_card(ease_factor=1.3)
    today = date(2026, 1, 1)
    for _ in range(5):
        review(card, quality=0, today=today)
    assert card.ease_factor >= 1.3


def test_is_due_and_due_cards():
    today = date(2026, 6, 1)
    not_due = make_card(card_id="a", due_date=date(2026, 6, 5))
    due_today = make_card(card_id="b", due_date=date(2026, 6, 1))
    overdue = make_card(card_id="c", due_date=date(2026, 5, 20))

    assert not is_due(not_due, today)
    assert is_due(due_today, today)
    assert is_due(overdue, today)

    result = due_cards([not_due, due_today, overdue], today)
    assert {c.card_id for c in result} == {"b", "c"}


def test_invalid_quality_raises():
    card = make_card()
    try:
        review(card, quality=6)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for out-of-range quality")
