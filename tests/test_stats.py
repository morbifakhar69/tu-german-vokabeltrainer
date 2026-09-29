"""Tests for stats summarization + plot generation."""

from vokabeltrainer.models import Card
from vokabeltrainer.stats import save_stats_plot, summarize


def make_cards():
    return [
        Card(card_id="a", german="Hund", english="dog", category="animals"),
        Card(card_id="b", german="helfen", english="to help", category="verbs"),
    ]


def test_summarize_empty_history():
    summary = summarize(make_cards(), [])
    assert summary.total_reviews == 0
    assert summary.accuracy == 0.0
    assert summary.weakest_category is None


def test_summarize_computes_accuracy_and_weakest_category():
    history = [
        ("a", 5, "2026-01-01"),
        ("a", 4, "2026-01-02"),
        ("b", 1, "2026-01-01"),
        ("b", 2, "2026-01-02"),
    ]
    summary = summarize(make_cards(), history)
    assert summary.total_reviews == 4
    assert summary.accuracy == 0.5  # 2 out of 4 were quality >= 3
    assert summary.accuracy_by_category["animals"] == 1.0
    assert summary.accuracy_by_category["verbs"] == 0.0
    assert summary.weakest_category == "verbs"


def test_save_stats_plot_creates_file(tmp_path):
    history = [
        ("a", 5, "2026-01-01"),
        ("a", 2, "2026-01-02"),
    ]
    out_path = tmp_path / "plots" / "review_stats.png"
    save_stats_plot(history, out_path)
    assert out_path.exists()
    assert out_path.stat().st_size > 0
