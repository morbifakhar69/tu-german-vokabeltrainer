"""Tests for question direction and human-friendly answer checking."""

from vokabeltrainer.models import Card
from vokabeltrainer.quiz import (
    ENGLISH_TO_GERMAN,
    GERMAN_TO_ENGLISH,
    answer_is_correct,
    normalize_answer,
    question_for,
)


def make_card(**overrides) -> Card:
    defaults = dict(
        card_id="hund",
        german="der Hund",
        english="dog",
        category="animals",
        word_type="noun",
        gender="der",
    )
    defaults.update(overrides)
    return Card(**defaults)


def test_question_supports_both_directions():
    card = make_card()

    german_answer = question_for(card, ENGLISH_TO_GERMAN)
    assert german_answer.prompt_label == "English"
    assert german_answer.prompt == "dog"
    assert german_answer.correct_answer == "der Hund"
    assert german_answer.answer_language == "de"

    verb = make_card(
        german="helfen",
        english="to help",
        word_type="verb",
        gender="",
        verb_case="dativ",
    )
    english_answer = question_for(verb, GERMAN_TO_ENGLISH)
    assert english_answer.prompt_label == "German"
    assert english_answer.prompt == "helfen (+Dativ)"
    assert english_answer.correct_answer == "to help"
    assert english_answer.answer_language == "en"


def test_normalization_handles_whitespace_case_unicode_and_umlaut_spelling():
    assert normalize_answer("  DIE   STRAẞE ", "de") == "die strasse"
    assert normalize_answer("FU\u0308NF", "de") == "fuenf"
    assert normalize_answer("  Good   Morning ", "en") == "good morning"


def test_german_noun_accepts_omitted_article_but_not_wrong_article():
    card = make_card(german="die Straße", gender="die")
    question = question_for(card, ENGLISH_TO_GERMAN)

    assert answer_is_correct("die Straße", question, card)
    assert answer_is_correct("STRASSE", question, card)
    assert not answer_is_correct("der Straße", question, card)


def test_answer_checking_preserves_meaningful_spelling_differences():
    card = make_card(
        german="schön",
        english="beautiful",
        word_type="adjective",
        gender="",
    )
    question = question_for(card, ENGLISH_TO_GERMAN)

    assert answer_is_correct("schoen", question, card)
    assert not answer_is_correct("schon", question, card)
    assert not answer_is_correct("schone", question, card)
