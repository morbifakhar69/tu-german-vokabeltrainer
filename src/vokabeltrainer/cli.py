"""Command line interface for the vocabulary trainer.

Kept as plain argparse (no extra CLI-framework dependency) since the
surface area here is small: five subcommands, each doing one thing.
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

from vokabeltrainer.dataset import categories as list_categories
from vokabeltrainer.dataset import default_dataset_path, load_cards
from vokabeltrainer.models import Card, ReviewResult
from vokabeltrainer.notifier import notify
from vokabeltrainer.scheduler import due_cards, review
from vokabeltrainer.stats import save_stats_plot, summarize
from vokabeltrainer.storage import ProgressStore

QUALITY_HELP = (
    "How well did you know it? 0 = no idea, 3 = correct but had to think, "
    "5 = instant recall  (q to stop)"
)


def _load(dataset: str | None, db: str | None) -> tuple[list[Card], ProgressStore]:
    dataset_path = Path(dataset) if dataset else default_dataset_path()
    cards = load_cards(dataset_path)
    store = ProgressStore(Path(db)) if db else ProgressStore()
    store.hydrate(cards)
    return cards, store


def _filter_category(cards: list[Card], category: str | None) -> list[Card]:
    if not category:
        return cards
    return [c for c in cards if c.category.lower() == category.lower()]


def cmd_categories(args: argparse.Namespace) -> None:
    cards, store = _load(args.dataset, args.db)
    store.close()
    counts: dict[str, int] = {}
    for c in cards:
        counts[c.category] = counts.get(c.category, 0) + 1
    for cat in list_categories(cards):
        print(f"{cat:<12} {counts[cat]} words")


def cmd_due(args: argparse.Namespace) -> None:
    cards, store = _load(args.dataset, args.db)
    store.close()
    cards = _filter_category(cards, args.category)
    due = due_cards(cards)
    print(f"{len(due)} of {len(cards)} card(s) due today.")
    for c in due[:20]:
        print(f"  - {c.german} {c.grammar_hint()} -> {c.english}  [{c.category}]")
    if len(due) > 20:
        print(f"  ... and {len(due) - 20} more")


def cmd_study(args: argparse.Namespace) -> None:
    cards, store = _load(args.dataset, args.db)
    cards = _filter_category(cards, args.category)

    pool = due_cards(cards) if not args.all else list(cards)
    if args.random:
        random.shuffle(pool)
    if args.limit:
        pool = pool[: args.limit]

    if not pool:
        print("Nothing to study right now - try again later or use --all.")
        store.close()
        return

    print(f"Studying {len(pool)} card(s). {QUALITY_HELP}\n")
    reviewed = 0
    for card in pool:
        print(f"{card.german} {card.grammar_hint()}")
        input("  (press Enter to reveal) ")
        example = f"\n  e.g. {card.example_de} - {card.example_en}" if card.example_de else ""
        print(f"  -> {card.english}{example}")

        answer = input("  quality [0-5, q]: ").strip().lower()
        if answer == "q":
            break
        try:
            quality = int(answer)
        except ValueError:
            print("  (not a number, skipping this card)")
            continue

        review(card, quality)
        store.save(card)
        store.log_review(ReviewResult(card_id=card.card_id, quality=quality))
        reviewed += 1
        print()

    print(f"Session done - reviewed {reviewed} card(s).")
    store.close()


def cmd_watch(args: argparse.Namespace) -> None:
    print(
        f"Watching for due cards every {args.interval} minute(s)."
        " Press Ctrl+C to stop.\n"
    )
    try:
        while True:
            cards, store = _load(args.dataset, args.db)
            store.close()
            cards = _filter_category(cards, args.category)
            due = due_cards(cards)

            timestamp = time.strftime("%H:%M:%S")
            if due:
                notify(
                    "Vokabeltrainer",
                    f"{len(due)} German word(s) are due for review.",
                )
                print(f"[{timestamp}] {len(due)} card(s) due - notification sent.")
            else:
                print(f"[{timestamp}] nothing due right now.")

            time.sleep(args.interval * 60)
    except KeyboardInterrupt:
        print("\nStopped watching.")


def cmd_stats(args: argparse.Namespace) -> None:
    cards, store = _load(args.dataset, args.db)
    history = store.review_history()
    store.close()

    summary = summarize(cards, history)
    print(f"Total reviews: {summary.total_reviews}")
    print(f"Overall accuracy (quality >= 3): {summary.accuracy:.0%}")
    print()
    print("Accuracy by category:")
    for cat, acc in summary.accuracy_by_category.items():
        print(f"  {cat:<12} {acc:.0%}")

    if summary.weakest_category:
        print(
            f"\nTip: your accuracy is lowest in '{summary.weakest_category}' - "
            "try `study --category "
            f"{summary.weakest_category}` for a focused session."
        )

    if history:
        out_path = Path(args.plot_dir) / "review_stats.png"
        save_stats_plot(history, out_path)
        print(f"\nSaved plot to {out_path}")
    else:
        print("\nNo reviews logged yet - study a few cards first to generate a plot.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vokabeltrainer",
        description="A small spaced-repetition German vocabulary trainer.",
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--dataset", help="Path to a vocabulary CSV (default: bundled demo dataset)"
    )
    common.add_argument("--db", help="Path to the progress database (default: ~/.vokabeltrainer)")

    sub = parser.add_subparsers(dest="command", required=True)

    p_study = sub.add_parser("study", parents=[common], help="Start an interactive review session")
    p_study.add_argument("--category", help="Only study cards from this category")
    p_study.add_argument("--random", action="store_true", help="Shuffle the study order")
    p_study.add_argument("--all", action="store_true", help="Include cards that aren't due yet")
    p_study.add_argument("--limit", type=int, help="Maximum number of cards to study")
    p_study.set_defaults(func=cmd_study)

    p_due = sub.add_parser("due", parents=[common], help="Show cards due for review today")
    p_due.add_argument("--category", help="Only count cards from this category")
    p_due.set_defaults(func=cmd_due)

    p_watch = sub.add_parser(
        "watch", parents=[common], help="Stay running and periodically notify about due cards"
    )
    p_watch.add_argument("--category", help="Only watch cards from this category")
    p_watch.add_argument(
        "--interval", type=float, default=30, help="Minutes between checks (default: 30)"
    )
    p_watch.set_defaults(func=cmd_watch)

    p_stats = sub.add_parser("stats", parents=[common], help="Show progress stats and save a plot")
    p_stats.add_argument("--plot-dir", default="plots", help="Directory to save the plot in")
    p_stats.set_defaults(func=cmd_stats)

    p_cats = sub.add_parser("categories", parents=[common], help="List available categories")
    p_cats.set_defaults(func=cmd_categories)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
