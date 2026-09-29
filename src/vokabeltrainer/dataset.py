"""Loading and validating vocabulary CSV files into Card objects."""

from __future__ import annotations

import csv
import hashlib
from importlib import resources
from pathlib import Path

from vokabeltrainer.models import Card

REQUIRED_COLUMNS = {"german", "english", "category"}


def _make_card_id(german: str, category: str) -> str:
    """Derive a stable id from the word + category.

    This is deliberately *not* a random id: if you re-import a bigger CSV
    later (e.g. your own 3000-word list) words that already existed keep
    their learning progress, since the id only depends on the content.
    """
    raw = f"{german.strip().lower()}::{category.strip().lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def load_cards(csv_path: Path | str) -> list[Card]:
    """Read a vocabulary CSV file and return a list of Card objects.

    Required columns: german, english, category
    Optional columns: word_type, gender, verb_case, example_de, example_en

    Raises ValueError if required columns are missing or a row is malformed.
    """
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{csv_path} looks empty")

        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"{csv_path} is missing required column(s): {sorted(missing)}")

        cards = []
        for line_no, row in enumerate(reader, start=2):  # header is line 1
            german = (row.get("german") or "").strip()
            english = (row.get("english") or "").strip()
            category = (row.get("category") or "").strip()
            if not german or not english or not category:
                raise ValueError(
                    f"{csv_path}:{line_no}: german/english/category can't be empty"
                )

            cards.append(
                Card(
                    card_id=_make_card_id(german, category),
                    german=german,
                    english=english,
                    category=category,
                    word_type=(row.get("word_type") or "").strip(),
                    gender=(row.get("gender") or "").strip(),
                    verb_case=(row.get("verb_case") or "").strip(),
                    example_de=(row.get("example_de") or "").strip(),
                    example_en=(row.get("example_en") or "").strip(),
                )
            )
    return cards


def default_dataset_path() -> Path:
    """Path to the small demo dataset bundled with the package.

    Swap this for your own (bigger) CSV with the same columns using the
    `--dataset` flag on the CLI - no code changes needed.
    """
    return Path(str(resources.files("vokabeltrainer.data").joinpath("vocabulary_demo.csv")))


def categories(cards: list[Card]) -> list[str]:
    """Sorted list of distinct categories present in a set of cards."""
    return sorted({c.category for c in cards})
