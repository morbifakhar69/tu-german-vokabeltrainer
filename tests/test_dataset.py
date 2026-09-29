"""Tests for CSV loading/validation."""

import pytest

from vokabeltrainer.dataset import categories, default_dataset_path, load_cards


def write_csv(tmp_path, content):
    path = tmp_path / "vocab.csv"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_cards_basic(tmp_path):
    path = write_csv(
        tmp_path,
        "german,english,category,word_type,gender,verb_case,example_de,example_en\n"
        "der Hund,dog,animals,noun,der,,Der Hund bellt.,The dog barks.\n"
        "helfen,to help,verbs,verb,,dativ,Ich helfe dir.,I help you.\n",
    )
    cards = load_cards(path)
    assert len(cards) == 2
    assert cards[0].german == "der Hund"
    assert cards[0].gender == "der"
    assert cards[1].verb_case == "dativ"


def test_missing_required_column_raises(tmp_path):
    path = write_csv(tmp_path, "german,english\nHund,dog\n")
    with pytest.raises(ValueError, match="missing required column"):
        load_cards(path)


def test_empty_required_field_raises(tmp_path):
    path = write_csv(
        tmp_path,
        "german,english,category\n,dog,animals\n",
    )
    with pytest.raises(ValueError, match="can't be empty"):
        load_cards(path)


def test_card_id_is_stable_across_reloads(tmp_path):
    path = write_csv(
        tmp_path,
        "german,english,category\nHund,dog,animals\n",
    )
    first = load_cards(path)[0].card_id
    second = load_cards(path)[0].card_id
    assert first == second


def test_default_dataset_loads_and_has_expected_categories():
    cards = load_cards(default_dataset_path())
    assert len(cards) > 100
    cats = categories(cards)
    assert "verbs" in cats
    assert "greetings" in cats
