"""Tests for question direction and human-friendly answer checking."""

import io
import random
import sys
import time

import pytest

from vokabeltrainer.models import Card
from vokabeltrainer.quiz import (
    DIRECTIONS,
    ENGLISH_TO_GERMAN,
    GERMAN_TO_ENGLISH,
    AnswerCountdown,
    QuizSession,
    answer_is_correct,
    normalize_answer,
    question_for,
    timed_input,
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


def test_seeded_sessions_choose_directions_deterministically():
    cards = [make_card(card_id=str(index)) for index in range(6)]

    def directions_for(seed):
        session = QuizSession(cards, rng=random.Random(seed))
        directions = []
        while not session.finished:
            question = session.current_question
            assert question is not None
            assert session.current_question is question
            directions.append(question.direction)
            session.submit_answer(question.correct_answer, elapsed_seconds=1)
        return directions

    first = directions_for(42)
    second = directions_for(42)

    assert first == second
    assert set(first) == set(DIRECTIONS)


def test_quiz_session_scores_wrong_and_late_answers():
    cards = [
        make_card(card_id="timely"),
        make_card(card_id="late"),
        make_card(card_id="wrong"),
    ]
    session = QuizSession(
        cards,
        time_limit_seconds=10,
        question_factory=lambda card: question_for(card, GERMAN_TO_ENGLISH),
    )

    timely = session.submit_answer("DOG", elapsed_seconds=2)
    late = session.submit_answer("dog", elapsed_seconds=10.1)
    wrong = session.submit_answer("cat", elapsed_seconds=3)
    results = session.final_results()

    assert timely.correct
    assert late.answer_matches and late.late and not late.correct
    assert not wrong.answer_matches and not wrong.correct
    assert results.total_questions == 3
    assert results.reviewed == 3
    assert results.score == 1
    assert results.incorrect == 2
    assert results.late_answers == 1
    assert results.remaining == 0
    assert results.accuracy == pytest.approx(1 / 3)


def test_quiz_session_tracks_timeout_and_rejects_premature_results():
    session = QuizSession(
        [make_card()],
        question_factory=lambda card: question_for(card, ENGLISH_TO_GERMAN),
    )

    with pytest.raises(RuntimeError, match="not finished"):
        session.final_results()

    timeout = session.record_timeout()

    assert timeout.answer is None
    assert timeout.late
    assert not timeout.correct
    assert session.final_results().late_answers == 1

    with pytest.raises(RuntimeError, match="already finished"):
        session.submit_answer("der Hund", elapsed_seconds=1)


def test_answer_countdown_has_beginner_friendly_visible_states():
    countdown = AnswerCountdown(10)

    assert countdown.remaining_seconds(0) == 10
    assert countdown.remaining_seconds(0.1) == 10
    assert countdown.remaining_seconds(1) == 9
    assert countdown.status(9.1) == "1s remaining"
    assert countdown.status(10) == "time's up - answer will be marked late"

    with pytest.raises(ValueError, match="greater than zero"):
        AnswerCountdown(0)


def test_countdown_warns_but_returns_redirected_input_after_deadline(
    capsys,
    monkeypatch,
):
    class DelayedInput(io.StringIO):
        def readline(self, *args, **kwargs):
            time.sleep(0.03)
            return super().readline(*args, **kwargs)

    monkeypatch.setattr(sys, "stdin", DelayedInput("dog\n"))

    answer = timed_input("Answer: ", timeout=0.01, continue_after_timeout=True)

    assert answer == "dog"
    assert "time's up - answer will be marked late" in capsys.readouterr().out
