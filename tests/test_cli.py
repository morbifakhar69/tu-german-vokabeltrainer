"""Tests for the CLI layer (argparse wiring + the subcommand functions)."""

from __future__ import annotations

import builtins

from vokabeltrainer.cli import build_parser, main
from vokabeltrainer.dataset import load_cards
from vokabeltrainer.quiz import (
    ENGLISH_TO_GERMAN,
    GERMAN_TO_ENGLISH,
    InputTimedOut,
    question_for,
)
from vokabeltrainer.storage import ProgressStore

SAMPLE_CSV = (
    "german,english,category,word_type,gender,verb_case,example_de,example_en\n"
    "der Hund,dog,animals,noun,der,,Der Hund bellt.,The dog barks.\n"
    "helfen,to help,verbs,verb,,dativ,Ich helfe dir.,I help you.\n"
    "die Katze,cat,animals,noun,die,,Die Katze schlaeft.,The cat sleeps.\n"
)


def make_dataset(tmp_path):
    path = tmp_path / "vocab.csv"
    path.write_text(SAMPLE_CSV, encoding="utf-8")
    return path


def test_categories_command(tmp_path, capsys):
    dataset = make_dataset(tmp_path)
    db = tmp_path / "progress.db"

    rc = main(["categories", "--dataset", str(dataset), "--db", str(db)])
    out = capsys.readouterr().out

    assert rc == 0
    assert "animals" in out
    assert "verbs" in out
    assert "2 words" in out  # two animal cards


def test_due_command_shows_all_cards_on_first_run(tmp_path, capsys):
    dataset = make_dataset(tmp_path)
    db = tmp_path / "progress.db"

    rc = main(["due", "--dataset", str(dataset), "--db", str(db)])
    out = capsys.readouterr().out

    assert rc == 0
    assert "3 of 3 card(s) due today" in out
    assert "helfen (+Dativ)" in out


def test_due_command_category_filter(tmp_path, capsys):
    dataset = make_dataset(tmp_path)
    db = tmp_path / "progress.db"

    main(["due", "--dataset", str(dataset), "--db", str(db), "--category", "verbs"])
    out = capsys.readouterr().out
    assert "1 of 1 card(s) due today" in out


def persisted_progress(dataset, db):
    cards = load_cards(dataset)
    with ProgressStore(db) as store:
        history = store.review_history()
        store.hydrate(cards)
    return cards, history


def test_study_correct_answer_grades_and_persists_progress(tmp_path, capsys, monkeypatch):
    dataset = make_dataset(tmp_path)
    db = tmp_path / "progress.db"

    monkeypatch.setattr(
        "vokabeltrainer.cli.question_for",
        lambda card: question_for(card, GERMAN_TO_ENGLISH),
    )
    monkeypatch.setattr("vokabeltrainer.cli.timed_input", lambda *_args: "  DOG ")

    rc = main(
        ["study", "--dataset", str(dataset), "--db", str(db), "--all", "--limit", "1"]
    )
    out = capsys.readouterr().out

    assert rc == 0
    assert "Correct!" in out
    assert "Correct answer: dog" in out
    assert "Session score: 1/1 (100%)" in out
    assert "1 reviewed card(s)" in out

    cards, history = persisted_progress(dataset, db)
    assert [quality for _card_id, quality, _date in history] == [5]
    assert cards[0].repetitions == 1

    main(["stats", "--dataset", str(dataset), "--db", str(db), "--plot-dir", str(tmp_path)])
    stats_out = capsys.readouterr().out
    assert "Total reviews: 1" in stats_out


def test_study_wrong_answer_allows_one_retry_but_persists_failure(
    tmp_path, capsys, monkeypatch
):
    dataset = make_dataset(tmp_path)
    db = tmp_path / "progress.db"

    monkeypatch.setattr(
        "vokabeltrainer.cli.question_for",
        lambda card: question_for(card, ENGLISH_TO_GERMAN),
    )
    monkeypatch.setattr("vokabeltrainer.cli.timed_input", lambda *_args: "die Katze")
    retries = iter(["  HUND "])
    monkeypatch.setattr(builtins, "input", lambda *_args: next(retries))

    rc = main(
        ["study", "--dataset", str(dataset), "--db", str(db), "--all", "--limit", "1"]
    )
    out = capsys.readouterr().out

    assert rc == 0
    assert "Incorrect." in out
    assert "Correct answer: der Hund" in out
    assert "Retry correct - good practice." in out
    assert "Session score: 0/1 (0%)" in out

    cards, history = persisted_progress(dataset, db)
    assert [quality for _card_id, quality, _date in history] == [1]
    assert cards[0].repetitions == 0
    assert cards[0].interval_days == 1


def test_study_timeout_reveals_answer_and_allows_untimed_retry(
    tmp_path, capsys, monkeypatch
):
    dataset = make_dataset(tmp_path)
    db = tmp_path / "progress.db"

    monkeypatch.setattr(
        "vokabeltrainer.cli.question_for",
        lambda card: question_for(card, GERMAN_TO_ENGLISH),
    )

    def time_out(*_args):
        raise InputTimedOut

    monkeypatch.setattr("vokabeltrainer.cli.timed_input", time_out)
    retries = iter(["dog"])
    monkeypatch.setattr(builtins, "input", lambda *_args: next(retries))

    rc = main(
        ["study", "--dataset", str(dataset), "--db", str(db), "--all", "--limit", "1"]
    )
    out = capsys.readouterr().out

    assert rc == 0
    assert out.index("Timed out.") < out.index("Correct answer: dog")
    assert "Retry correct - good practice." in out
    assert "Session score: 0/1 (0%)" in out

    _cards, history = persisted_progress(dataset, db)
    assert [quality for _card_id, quality, _date in history] == [1]


def test_study_quit_before_answer_does_not_record_review(tmp_path, capsys, monkeypatch):
    dataset = make_dataset(tmp_path)
    db = tmp_path / "progress.db"
    monkeypatch.setattr("vokabeltrainer.cli.timed_input", lambda *_args: "quit")

    rc = main(
        ["study", "--dataset", str(dataset), "--db", str(db), "--all", "--limit", "1"]
    )
    out = capsys.readouterr().out

    assert rc == 0
    assert "0 reviewed card(s)" in out
    _cards, history = persisted_progress(dataset, db)
    assert history == []


def test_study_question_count_defaults_and_aliases():
    parser = build_parser()

    assert parser.parse_args(["study"]).limit == 10
    assert parser.parse_args(["study", "--questions", "4"]).limit == 4
    assert parser.parse_args(["study", "--limit", "5"]).limit == 5


def test_study_accepts_late_input_and_reports_it(tmp_path, capsys, monkeypatch):
    dataset = make_dataset(tmp_path)
    db = tmp_path / "progress.db"

    monkeypatch.setattr(
        "vokabeltrainer.cli.question_for",
        lambda card: question_for(card, GERMAN_TO_ENGLISH),
    )
    monkeypatch.setattr("vokabeltrainer.cli.timed_input", lambda *_args: "dog")
    monotonic_values = iter([100.0, 110.1])
    monkeypatch.setattr(
        "vokabeltrainer.cli.time.monotonic",
        lambda: next(monotonic_values),
    )
    monkeypatch.setattr(builtins, "input", lambda *_args: "dog")

    rc = main(
        ["study", "--dataset", str(dataset), "--db", str(db), "--all", "--questions", "1"]
    )
    out = capsys.readouterr().out

    assert rc == 0
    assert "Your answer matches, but late answers do not score." in out
    assert "1 late answer(s)." in out
    _cards, history = persisted_progress(dataset, db)
    assert [quality for _card_id, quality, _date in history] == [1]


def test_add_word_appends_a_row(tmp_path, capsys):
    dataset = make_dataset(tmp_path)
    db = tmp_path / "progress.db"

    rc = main(
        [
            "add-word",
            "das Fenster",
            "window",
            "home",
            "--word-type",
            "noun",
            "--gender",
            "das",
            "--dataset",
            str(dataset),
            "--db",
            str(db),
        ]
    )
    assert rc == 0
    assert "Added 'das Fenster' -> 'window'" in capsys.readouterr().out

    # the new word should now show up via `categories`
    main(["categories", "--dataset", str(dataset), "--db", str(db)])
    out = capsys.readouterr().out
    assert "home" in out


def test_missing_dataset_file_gives_friendly_error(tmp_path, capsys):
    missing = tmp_path / "does_not_exist.csv"
    db = tmp_path / "progress.db"

    rc = main(["categories", "--dataset", str(missing), "--db", str(db)])
    err = capsys.readouterr().err

    assert rc == 1
    assert "error:" in err
