"""Vokabeltrainer: a small spaced-repetition German vocabulary trainer.

Public API re-exported here so you can do e.g.:

    from vokabeltrainer import Card, ProgressStore, load_cards, review
"""

from vokabeltrainer.dataset import categories, default_dataset_path, load_cards
from vokabeltrainer.models import Card, ReviewResult
from vokabeltrainer.scheduler import due_cards, is_due, review
from vokabeltrainer.stats import StatsSummary, summarize
from vokabeltrainer.storage import ProgressStore

__all__ = [
    "Card",
    "ReviewResult",
    "review",
    "is_due",
    "due_cards",
    "load_cards",
    "categories",
    "default_dataset_path",
    "ProgressStore",
    "summarize",
    "StatsSummary",
]

__version__ = "0.1.0"
