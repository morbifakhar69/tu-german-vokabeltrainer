"""Tests for CSV loading/validation."""

import pytest

from vokabeltrainer import Card, FlashCard, VocabularyBank
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


def test_empty_file_raises_clear_error(tmp_path):
    path = write_csv(tmp_path, "")

    with pytest.raises(ValueError, match="looks empty"):
        load_cards(path)


def test_utf8_byte_order_mark_is_accepted(tmp_path):
    path = write_csv(
        tmp_path,
        "\ufeffgerman,english,category\nHund,dog,animals\n",
    )

    cards = load_cards(path)

    assert len(cards) == 1
    assert cards[0].german == "Hund"


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


def test_public_flashcard_name_preserves_card_compatibility():
    assert Card is FlashCard


def test_vocabulary_bank_loads_csv_as_typed_sequence(tmp_path):
    path = write_csv(
        tmp_path,
        "german,english,category\n"
        "Hallo,hello,greetings\n"
        "Hund,dog,animals\n",
    )

    bank = VocabularyBank.from_csv(path)

    assert len(bank) == 2
    assert isinstance(bank[0], FlashCard)
    assert bank[0].german == "Hallo"
    assert bank.categories == ("animals", "greetings")
    assert isinstance(bank[:1], tuple)


def test_beginner_vocabulary_bank_uses_bundled_dataset():
    bank = VocabularyBank.beginner()

    assert len(bank) > 100
    assert "greetings" in bank.categories
    assert all(card.german and card.english for card in bank)
