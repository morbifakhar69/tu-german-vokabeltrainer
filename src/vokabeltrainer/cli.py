"""Command line interface for the vocabulary trainer.

Kept as plain argparse (no extra CLI-framework dependency) since the
surface area here is small: five subcommands, each doing one thing.
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from vokabeltrainer.dataset import categories as list_categories
from vokabeltrainer.dataset import default_dataset_path, load_cards
from vokabeltrainer.models import Card, ReviewResult
from vokabeltrainer.notifier import notify
from vokabeltrainer.quiz import (
    FAILURE_QUALITY,
    FIRST_ATTEMPT_SECONDS,
    SUCCESS_QUALITY,
    InputTimedOut,
    Question,
    answer_is_correct,
    is_quit_command,
    question_for,
    timed_input,
)
from vokabeltrainer.scheduler import due_cards, review
from vokabeltrainer.stats import save_stats_plot, summarize
from vokabeltrainer.storage import ProgressStore


@dataclass(frozen=True)
class StudyOutcome:
    quality: int | None
    stop_requested: bool = False


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


def _print_canonical_answer(card: Card, question: Question) -> None:
    print(f"  Correct answer: {question.correct_answer}")
    if card.example_de:
        print(f"  Example: {card.example_de} - {card.example_en}")


def _practice_retry(card: Card, question: Question) -> bool:
    try:
        retry = input("  Retry (untimed, q to quit): ")
    except EOFError:
        print("\n  Input closed; ending the session.")
        return True

    if is_quit_command(retry):
        print("  Ending the session; the first attempt remains graded as incorrect.")
        return True
    if answer_is_correct(retry, question, card):
        print("  Retry correct - good practice.")
    else:
        print(f"  Retry incorrect. The answer is {question.correct_answer}.")
    return False


def _quiz_card(card: Card) -> StudyOutcome:
    question = question_for(card)
    print(f"{question.prompt_label}: {question.prompt}")

    try:
        answer = timed_input(
            f"  Your answer ({FIRST_ATTEMPT_SECONDS}s, q to quit): ",
            FIRST_ATTEMPT_SECONDS,
        )
    except InputTimedOut:
        print("  Timed out.")
        _print_canonical_answer(card, question)
        return StudyOutcome(FAILURE_QUALITY, _practice_retry(card, question))
    except EOFError:
        print("  Input closed; ending the session.")
        return StudyOutcome(None, True)

    if is_quit_command(answer):
        return StudyOutcome(None, True)
    if answer_is_correct(answer, question, card):
        print("  Correct!")
        _print_canonical_answer(card, question)
        return StudyOutcome(SUCCESS_QUALITY)

    print("  Incorrect.")
    _print_canonical_answer(card, question)
    return StudyOutcome(FAILURE_QUALITY, _practice_retry(card, question))


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

    print(
        f"Studying {len(pool)} typed-answer card(s). "
        f"You have {FIRST_ATTEMPT_SECONDS} seconds for each first attempt.\n"
    )
    reviewed = 0
    correct = 0
    for card in pool:
        outcome = _quiz_card(card)
        if outcome.quality is not None:
            review(card, outcome.quality)
            store.save(card)
            store.log_review(ReviewResult(card_id=card.card_id, quality=outcome.quality))
            reviewed += 1
            correct += outcome.quality == SUCCESS_QUALITY
            percentage = correct / reviewed
            print(f"  Session score: {correct}/{reviewed} ({percentage:.0%})\n")
        if outcome.stop_requested:
            break

    print(
        f"Session done - {correct}/{reviewed} correct across "
        f"{reviewed} reviewed card(s)."
    )
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
    print(f"Overall first-attempt accuracy: {summary.accuracy:.0%}")
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


def cmd_add(args: argparse.Namespace) -> None:
    dataset_path = Path(args.dataset) if args.dataset else default_dataset_path()
    if not dataset_path.exists():
        print(f"error: dataset file not found at {dataset_path}", file=sys.stderr)
        raise SystemExit(1)

    with open(dataset_path, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))

    row = {
        "german": args.german,
        "english": args.english,
        "category": args.category,
        "word_type": args.word_type or "",
        "gender": args.gender or "",
        "verb_case": args.verb_case or "",
        "example_de": args.example_de or "",
        "example_en": args.example_en or "",
    }

    with open(dataset_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writerow({col: row.get(col, "") for col in header})

    print(f"Added '{args.german}' -> '{args.english}' to {dataset_path}")


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

    p_study = sub.add_parser(
        "study", parents=[common], help="Start a timed typed-answer flashcard quiz"
    )
    p_study.add_argument("--category", help="Only study cards from this category")
    p_study.add_argument("--random", action="store_true", help="Shuffle the card order")
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

    p_add = sub.add_parser(
        "add-word", parents=[common], help="Append a new word to a vocabulary CSV"
    )
    p_add.add_argument("german", help="The German word or phrase")
    p_add.add_argument("english", help="The English translation")
    p_add.add_argument("category", help="Topic/category for this word")
    p_add.add_argument("--word-type", dest="word_type", help="noun/verb/adjective/phrase/...")
    p_add.add_argument("--gender", choices=["der", "die", "das"], help="Article, for nouns")
    p_add.add_argument(
        "--verb-case",
        dest="verb_case",
        choices=["akkusativ", "dativ"],
        help="Case this verb always governs",
    )
    p_add.add_argument("--example-de", dest="example_de", help="Example sentence in German")
    p_add.add_argument("--example-en", dest="example_en", help="Example sentence in English")
    p_add.set_defaults(func=cmd_add)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
