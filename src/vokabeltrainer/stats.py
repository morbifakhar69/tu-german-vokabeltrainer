"""Turning raw review history into human-readable stats and a plot."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: we only ever save plots to a file, never show them
import matplotlib.pyplot as plt

from vokabeltrainer.models import Card

ReviewRow = tuple[str, int, str]  # (card_id, quality, reviewed_on)


@dataclass
class StatsSummary:
    total_reviews: int
    accuracy: float  # fraction of reviews with quality >= 3
    accuracy_by_category: dict[str, float]
    weakest_category: str | None


def summarize(cards: list[Card], history: list[ReviewRow]) -> StatsSummary:
    """Compute overall + per-category accuracy from the review log."""
    card_category = {c.card_id: c.category for c in cards}

    if not history:
        return StatsSummary(
            total_reviews=0, accuracy=0.0, accuracy_by_category={}, weakest_category=None
        )

    correct_by_cat: dict[str, int] = defaultdict(int)
    total_by_cat: dict[str, int] = defaultdict(int)
    total_correct = 0

    for card_id, quality, _reviewed_on in history:
        category = card_category.get(card_id, "unknown")
        total_by_cat[category] += 1
        if quality >= 3:
            correct_by_cat[category] += 1
            total_correct += 1

    accuracy_by_category = {
        cat: correct_by_cat[cat] / total_by_cat[cat] for cat in sorted(total_by_cat)
    }
    weakest_category = (
        min(accuracy_by_category, key=lambda cat: accuracy_by_category[cat])
        if accuracy_by_category
        else None
    )

    return StatsSummary(
        total_reviews=len(history),
        accuracy=total_correct / len(history),
        accuracy_by_category=accuracy_by_category,
        weakest_category=weakest_category,
    )


def save_stats_plot(history: list[ReviewRow], out_path: Path) -> None:
    """Save a two-panel PNG: reviews per day, and accuracy per day."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    reviews_per_day: dict[str, list[int]] = defaultdict(list)
    for _card_id, quality, reviewed_on in history:
        reviews_per_day[reviewed_on].append(quality)

    days = sorted(reviews_per_day)
    counts = [len(reviews_per_day[d]) for d in days]
    accuracy = [
        sum(1 for q in reviews_per_day[d] if q >= 3) / len(reviews_per_day[d]) for d in days
    ]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)

    ax1.bar(days, counts, color="steelblue")
    ax1.set_ylabel("reviews")
    ax1.set_title("Reviews per day")

    ax2.plot(days, [a * 100 for a in accuracy], marker="o", color="seagreen")
    ax2.set_ylabel("accuracy (%)")
    ax2.set_ylim(0, 105)
    ax2.set_title("Accuracy per day")
    ax2.tick_params(axis="x", rotation=45)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
