"""Tests for the SQLite progress store."""

from datetime import date

from vokabeltrainer.models import Card, ReviewResult
from vokabeltrainer.storage import ProgressStore


def make_card(card_id="abc123") -> Card:
    return Card(card_id=card_id, german="Hund", english="dog", category="animals")


def test_save_and_hydrate_roundtrip(tmp_path):
    db_path = tmp_path / "progress.db"

    with ProgressStore(db_path) as store:
        card = make_card()
        card.ease_factor = 2.7
        card.interval_days = 6
        card.repetitions = 2
        card.due_date = date(2026, 3, 1)
        store.save(card)

    # fresh store instance, simulating the next time the app is started
    with ProgressStore(db_path) as store:
        fresh_card = make_card()  # default scheduling state
        store.hydrate([fresh_card])
        assert fresh_card.ease_factor == 2.7
        assert fresh_card.interval_days == 6
        assert fresh_card.repetitions == 2
        assert fresh_card.due_date == date(2026, 3, 1)


def test_hydrate_leaves_unknown_cards_untouched(tmp_path):
    store = ProgressStore(tmp_path / "progress.db")
    card = make_card(card_id="never_reviewed")
    store.hydrate([card])
    assert card.repetitions == 0  # untouched default
    store.close()


def test_log_review_and_history(tmp_path):
    store = ProgressStore(tmp_path / "progress.db")
    store.log_review(ReviewResult(card_id="a", quality=4, reviewed_on=date(2026, 1, 1)))
    store.log_review(ReviewResult(card_id="b", quality=2, reviewed_on=date(2026, 1, 2)))

    history = store.review_history()
    assert history == [
        ("a", 4, "2026-01-01"),
        ("b", 2, "2026-01-02"),
    ]
    store.close()


def test_save_upserts_existing_card(tmp_path):
    store = ProgressStore(tmp_path / "progress.db")
    card = make_card()
    card.repetitions = 1
    store.save(card)

    card.repetitions = 5
    store.save(card)

    fresh_card = make_card()
    store.hydrate([fresh_card])
    assert fresh_card.repetitions == 5
    store.close()
