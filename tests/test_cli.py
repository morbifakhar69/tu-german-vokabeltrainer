"""Tests for the CLI layer (argparse wiring + the subcommand functions)."""

from __future__ import annotations

import builtins

from vokabeltrainer.cli import main

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


def test_study_command_records_progress(tmp_path, capsys, monkeypatch):
    dataset = make_dataset(tmp_path)
    db = tmp_path / "progress.db"

    # simulate: reveal (Enter), rate 5, reveal (Enter), rate 4, reveal, rate 3
    answers = iter(["", "5", "", "4", "", "3"])
    monkeypatch.setattr(builtins, "input", lambda *_args: next(answers))

    rc = main(["study", "--dataset", str(dataset), "--db", str(db), "--all"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "reviewed 3 card(s)" in out

    # a second stats run should now see 3 logged reviews
    main(["stats", "--dataset", str(dataset), "--db", str(db), "--plot-dir", str(tmp_path)])
    stats_out = capsys.readouterr().out
    assert "Total reviews: 3" in stats_out


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
