"""Vokabeltrainer: a small spaced-repetition German vocabulary trainer.

Public API re-exported here so you can do e.g.:

    from vokabeltrainer import FlashCard, VocabularyBank
"""

from vokabeltrainer.dataset import (
    VocabularyBank,
    categories,
    default_dataset_path,
    load_cards,
)
from vokabeltrainer.models import Card, FlashCard, ReviewResult
from vokabeltrainer.quiz import (
    AnswerCountdown,
    AnswerResult,
    Question,
    QuizResults,
    QuizSession,
    answer_is_correct,
    choose_direction,
    normalize_answer,
    question_for,
)
from vokabeltrainer.scheduler import due_cards, is_due, review
from vokabeltrainer.stats import StatsSummary, summarize
from vokabeltrainer.storage import ProgressStore

__all__ = [
    "Card",
    "FlashCard",
    "VocabularyBank",
    "Question",
    "AnswerCountdown",
    "AnswerResult",
    "QuizResults",
    "QuizSession",
    "ReviewResult",
    "choose_direction",
    "question_for",
    "normalize_answer",
    "answer_is_correct",
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
