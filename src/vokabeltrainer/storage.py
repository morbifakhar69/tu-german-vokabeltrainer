"""SQLite-backed persistence for review progress and history.

The vocabulary itself lives in a plain CSV (easy to edit/extend). Only the
*progress* - ease factor, due dates, and the log of past reviews - is
stored here, in a small local SQLite database. That way, re-importing a
bigger CSV later doesn't wipe out what you've already learned, as long as
the words (and their card ids) stay the same.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from vokabeltrainer.models import Card, ReviewResult

DEFAULT_DB_PATH = Path.home() / ".vokabeltrainer" / "progress.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS progress (
    card_id TEXT PRIMARY KEY,
    ease_factor REAL NOT NULL,
    interval_days INTEGER NOT NULL,
    repetitions INTEGER NOT NULL,
    due_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    quality INTEGER NOT NULL,
    reviewed_on TEXT NOT NULL
);
"""


class ProgressStore:
    """Thin wrapper around a small SQLite database.

    Usage:
        store = ProgressStore()
        cards = load_cards(default_dataset_path())
        store.hydrate(cards)          # apply saved progress onto the cards
        ...                           # study session happens here
        store.save(card)              # after each review
        store.log_review(result)
    """

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ProgressStore:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def hydrate(self, cards: list[Card]) -> None:
        """Overwrite each card's scheduling fields with saved progress, if any."""
        rows = self._conn.execute(
            "SELECT card_id, ease_factor, interval_days, repetitions, due_date FROM progress"
        ).fetchall()
        saved = {row[0]: row[1:] for row in rows}
        for card in cards:
            if card.card_id in saved:
                ease, interval, reps, due = saved[card.card_id]
                card.ease_factor = ease
                card.interval_days = interval
                card.repetitions = reps
                card.due_date = date.fromisoformat(due)

    def save(self, card: Card) -> None:
        self._conn.execute(
            """
            INSERT INTO progress (card_id, ease_factor, interval_days, repetitions, due_date)
            VALUES (:card_id, :ease_factor, :interval_days, :repetitions, :due_date)
            ON CONFLICT(card_id) DO UPDATE SET
                ease_factor = excluded.ease_factor,
                interval_days = excluded.interval_days,
                repetitions = excluded.repetitions,
                due_date = excluded.due_date
            """,
            {
                "card_id": card.card_id,
                "ease_factor": card.ease_factor,
                "interval_days": card.interval_days,
                "repetitions": card.repetitions,
                "due_date": card.due_date.isoformat(),
            },
        )
        self._conn.commit()

    def log_review(self, result: ReviewResult) -> None:
        self._conn.execute(
            "INSERT INTO reviews (card_id, quality, reviewed_on) VALUES (?, ?, ?)",
            (result.card_id, result.quality, result.reviewed_on.isoformat()),
        )
        self._conn.commit()

    def review_history(self) -> list[tuple[str, int, str]]:
        """All logged reviews as (card_id, quality, reviewed_on) tuples, oldest first."""
        return self._conn.execute(
            "SELECT card_id, quality, reviewed_on FROM reviews ORDER BY reviewed_on"
        ).fetchall()
