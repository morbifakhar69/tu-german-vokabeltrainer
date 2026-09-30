"""Typed-answer quiz helpers, including cross-platform timed terminal input."""

from __future__ import annotations

import math
import os
import queue
import random
import sys
import threading
import time
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from vokabeltrainer.models import Card

ENGLISH_TO_GERMAN = "english_to_german"
GERMAN_TO_ENGLISH = "german_to_english"
DIRECTIONS = (ENGLISH_TO_GERMAN, GERMAN_TO_ENGLISH)

FIRST_ATTEMPT_SECONDS = 10
SUCCESS_QUALITY = 5
FAILURE_QUALITY = 1


class InputTimedOut(Exception):
    """Raised when no complete answer is entered before the deadline."""


@dataclass(frozen=True)
class AnswerCountdown:
    """Formatting and timing state for a visible answer countdown."""

    limit_seconds: float = FIRST_ATTEMPT_SECONDS

    def __post_init__(self) -> None:
        if self.limit_seconds <= 0:
            raise ValueError("time limit must be greater than zero")

    def remaining_seconds(self, elapsed_seconds: float) -> int:
        if elapsed_seconds < 0:
            raise ValueError("elapsed time cannot be negative")
        return max(0, math.ceil(self.limit_seconds - elapsed_seconds))

    def status(self, elapsed_seconds: float) -> str:
        remaining = self.remaining_seconds(elapsed_seconds)
        if remaining:
            return f"{remaining}s remaining"
        return "time's up - answer will be marked late"


@dataclass(frozen=True)
class Question:
    direction: str
    prompt_label: str
    prompt: str
    answer_language: str
    correct_answer: str


def choose_direction(rng: random.Random | None = None) -> str:
    """Choose a study direction, optionally using a seeded random generator."""
    return (rng.choice if rng is not None else random.choice)(DIRECTIONS)


def question_for(
    card: Card,
    direction: str | None = None,
    *,
    rng: random.Random | None = None,
) -> Question:
    """Build a question in one of the two study directions."""
    direction = direction if direction is not None else choose_direction(rng)

    if direction == ENGLISH_TO_GERMAN:
        return Question(
            direction=direction,
            prompt_label="English",
            prompt=card.english,
            answer_language="de",
            correct_answer=card.german,
        )
    if direction == GERMAN_TO_ENGLISH:
        hint = f"(+{card.verb_case.capitalize()})" if card.verb_case else ""
        return Question(
            direction=direction,
            prompt_label="German",
            prompt=f"{card.german} {hint}".strip(),
            answer_language="en",
            correct_answer=card.english,
        )
    raise ValueError(f"unknown quiz direction: {direction}")


def normalize_answer(answer: str, language: str) -> str:
    """Normalize small typing differences without doing fuzzy matching."""
    normalized = unicodedata.normalize("NFKC", answer).strip().casefold()
    normalized = " ".join(normalized.split())

    if language == "de":
        normalized = (
            normalized.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
        )
    return normalized


def answer_is_correct(answer: str, question: Question, card: Card) -> bool:
    """Return whether an answer matches the question's accepted spelling."""
    normalized_answer = normalize_answer(answer, question.answer_language)
    accepted = {normalize_answer(question.correct_answer, question.answer_language)}

    if question.answer_language == "de" and card.word_type.casefold() == "noun":
        words = question.correct_answer.strip().split(maxsplit=1)
        if len(words) == 2 and words[0].casefold() in {"der", "die", "das"}:
            accepted.add(normalize_answer(words[1], "de"))
        elif card.gender:
            accepted.add(normalize_answer(f"{card.gender} {question.correct_answer}", "de"))

    return normalized_answer in accepted


@dataclass(frozen=True)
class AnswerResult:
    """The graded first attempt for one flashcard."""

    card: Card
    question: Question
    answer: str | None
    answer_matches: bool
    correct: bool
    late: bool
    elapsed_seconds: float

    @property
    def quality(self) -> int:
        """SM-2 quality used by the existing scheduler."""
        return SUCCESS_QUALITY if self.correct else FAILURE_QUALITY


@dataclass(frozen=True)
class QuizResults:
    """A score snapshot for a quiz session."""

    total_questions: int
    reviewed: int
    score: int
    incorrect: int
    late_answers: int
    remaining: int

    @property
    def accuracy(self) -> float:
        """Correct-answer ratio, or zero before any answers."""
        return self.score / self.reviewed if self.reviewed else 0.0


class QuizSession:
    """Reusable state and scoring for a sequence of typed-answer questions."""

    def __init__(
        self,
        cards: Iterable[Card],
        *,
        time_limit_seconds: float = FIRST_ATTEMPT_SECONDS,
        rng: random.Random | None = None,
        question_factory: Callable[[Card], Question] | None = None,
    ) -> None:
        if time_limit_seconds <= 0:
            raise ValueError("time limit must be greater than zero")

        self._cards = tuple(cards)
        self._time_limit_seconds = time_limit_seconds
        self._rng = rng if rng is not None else random.Random()
        self._question_factory = question_factory
        self._answers: list[AnswerResult] = []
        self._current_question: Question | None = None

    @property
    def time_limit_seconds(self) -> float:
        return self._time_limit_seconds

    @property
    def finished(self) -> bool:
        return len(self._answers) == len(self._cards)

    @property
    def current_card(self) -> Card | None:
        if self.finished:
            return None
        return self._cards[len(self._answers)]

    @property
    def current_question(self) -> Question | None:
        card = self.current_card
        if card is None:
            return None
        if self._current_question is None:
            if self._question_factory is None:
                self._current_question = question_for(card, rng=self._rng)
            else:
                self._current_question = self._question_factory(card)
        return self._current_question

    @property
    def answer_history(self) -> tuple[AnswerResult, ...]:
        return tuple(self._answers)

    @property
    def results(self) -> QuizResults:
        reviewed = len(self._answers)
        score = sum(result.correct for result in self._answers)
        late_answers = sum(result.late for result in self._answers)
        return QuizResults(
            total_questions=len(self._cards),
            reviewed=reviewed,
            score=score,
            incorrect=reviewed - score,
            late_answers=late_answers,
            remaining=len(self._cards) - reviewed,
        )

    def submit_answer(self, answer: str, elapsed_seconds: float) -> AnswerResult:
        """Grade and record the current answer."""
        if elapsed_seconds < 0:
            raise ValueError("elapsed time cannot be negative")

        card, question = self._active_question()
        late = elapsed_seconds >= self._time_limit_seconds
        answer_matches = answer_is_correct(answer, question, card)
        return self._record(
            card=card,
            question=question,
            answer=answer,
            answer_matches=answer_matches,
            correct=answer_matches and not late,
            late=late,
            elapsed_seconds=elapsed_seconds,
        )

    def record_timeout(self) -> AnswerResult:
        """Record the current question as unanswered and late."""
        card, question = self._active_question()
        return self._record(
            card=card,
            question=question,
            answer=None,
            answer_matches=False,
            correct=False,
            late=True,
            elapsed_seconds=self._time_limit_seconds,
        )

    def final_results(self) -> QuizResults:
        """Return results after every question has been answered."""
        if not self.finished:
            raise RuntimeError("quiz session is not finished")
        return self.results

    def _active_question(self) -> tuple[Card, Question]:
        card = self.current_card
        question = self.current_question
        if card is None or question is None:
            raise RuntimeError("quiz session is already finished")
        return card, question

    def _record(
        self,
        *,
        card: Card,
        question: Question,
        answer: str | None,
        answer_matches: bool,
        correct: bool,
        late: bool,
        elapsed_seconds: float,
    ) -> AnswerResult:
        result = AnswerResult(
            card=card,
            question=question,
            answer=answer,
            answer_matches=answer_matches,
            correct=correct,
            late=late,
            elapsed_seconds=elapsed_seconds,
        )
        self._answers.append(result)
        self._current_question = None
        return result


def is_quit_command(answer: str) -> bool:
    return answer.strip().casefold() in {"q", "quit"}


def timed_input(
    prompt: str,
    timeout: float = FIRST_ATTEMPT_SECONDS,
    continue_after_timeout: bool = False,
) -> str:
    """Read a terminal line, optionally continuing after a visible countdown."""
    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")

    if continue_after_timeout:
        countdown = AnswerCountdown(timeout)
        try:
            if sys.stdin.isatty():
                if os.name == "nt":
                    answer = _countdown_windows_console_input(prompt, countdown)
                else:
                    answer = _countdown_posix_input(prompt, countdown)
            else:
                answer = _countdown_stream_input(prompt, countdown)
        except (EOFError, KeyboardInterrupt):
            print()
            raise

        print()
        return answer

    print(prompt, end="", flush=True)
    try:
        if os.name == "nt" and sys.stdin.isatty():
            answer = _timed_windows_console_input(timeout)
        elif os.name != "nt":
            answer = _timed_posix_input(timeout)
        else:
            answer = _timed_thread_input(timeout)
    except (EOFError, InputTimedOut, KeyboardInterrupt):
        print()
        raise

    print()
    return answer


def _render_countdown_line(
    prompt: str,
    countdown: AnswerCountdown,
    elapsed_seconds: float,
    characters: list[str],
) -> str:
    status = countdown.status(elapsed_seconds)
    line = f"{prompt}[{status}] {''.join(characters)}"
    print(
        f"\r{line}   \b\b\b",
        end="",
        flush=True,
    )
    return status


def _countdown_windows_console_input(
    prompt: str,
    countdown: AnswerCountdown,
) -> str:
    import msvcrt

    characters: list[str] = []
    started_at = time.monotonic()
    displayed_status = ""

    while True:
        elapsed_seconds = time.monotonic() - started_at
        status = countdown.status(elapsed_seconds)
        if status != displayed_status:
            displayed_status = _render_countdown_line(
                prompt,
                countdown,
                elapsed_seconds,
                characters,
            )

        if not msvcrt.kbhit():
            time.sleep(0.01)
            continue

        character = msvcrt.getwch()
        if character in {"\r", "\n"}:
            return "".join(characters)
        if character == "\x03":
            raise KeyboardInterrupt
        if character == "\x1a" and not characters:
            raise EOFError
        if character in {"\x00", "\xe0"}:
            msvcrt.getwch()
            continue
        if character == "\b":
            if characters:
                characters.pop()
                displayed_status = ""
            continue

        characters.append(character)
        displayed_status = ""


def _countdown_posix_input(prompt: str, countdown: AnswerCountdown) -> str:
    import select
    import termios
    import tty

    file_descriptor = sys.stdin.fileno()
    previous_settings = termios.tcgetattr(file_descriptor)
    characters: list[str] = []
    started_at = time.monotonic()
    displayed_status = ""

    try:
        tty.setcbreak(file_descriptor)
        while True:
            elapsed_seconds = time.monotonic() - started_at
            status = countdown.status(elapsed_seconds)
            if status != displayed_status:
                displayed_status = _render_countdown_line(
                    prompt,
                    countdown,
                    elapsed_seconds,
                    characters,
                )

            ready, _, _ = select.select([sys.stdin], [], [], 0.1)
            if not ready:
                continue

            character = sys.stdin.read(1)
            if character in {"\r", "\n"}:
                return "".join(characters)
            if character == "\x03":
                raise KeyboardInterrupt
            if character == "\x04":
                if not characters:
                    raise EOFError
                return "".join(characters)
            if character in {"\x7f", "\b"}:
                if characters:
                    characters.pop()
                    displayed_status = ""
                continue

            characters.append(character)
            displayed_status = ""
    finally:
        termios.tcsetattr(file_descriptor, termios.TCSADRAIN, previous_settings)


def _countdown_stream_input(prompt: str, countdown: AnswerCountdown) -> str:
    stop_countdown = threading.Event()
    print(f"{prompt}[{countdown.status(0)}] ", end="", flush=True)

    def warn_at_deadline() -> None:
        if not stop_countdown.wait(countdown.limit_seconds):
            print(f"\n  {countdown.status(countdown.limit_seconds)}", flush=True)

    warning_thread = threading.Thread(target=warn_at_deadline, daemon=True)
    warning_thread.start()
    try:
        answer = sys.stdin.readline()
    finally:
        stop_countdown.set()
        warning_thread.join(timeout=0.1)

    if answer == "":
        raise EOFError
    return answer.rstrip("\r\n")


def _timed_windows_console_input(timeout: float) -> str:
    import msvcrt

    characters: list[str] = []
    deadline = time.monotonic() + timeout

    while True:
        if time.monotonic() >= deadline:
            raise InputTimedOut
        if not msvcrt.kbhit():
            time.sleep(0.01)
            continue

        character = msvcrt.getwch()
        if character in {"\r", "\n"}:
            return "".join(characters)
        if character == "\x03":
            raise KeyboardInterrupt
        if character == "\x1a" and not characters:
            raise EOFError
        if character in {"\x00", "\xe0"}:
            msvcrt.getwch()
            continue
        if character == "\b":
            if characters:
                characters.pop()
                print("\b \b", end="", flush=True)
            continue

        characters.append(character)
        print(character, end="", flush=True)


def _timed_posix_input(timeout: float) -> str:
    import select

    if not sys.stdin.isatty():
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if not ready:
            raise InputTimedOut
        answer = sys.stdin.readline()
        if answer == "":
            raise EOFError
        return answer.rstrip("\r\n")

    import termios
    import tty

    file_descriptor = sys.stdin.fileno()
    previous_settings = termios.tcgetattr(file_descriptor)
    characters: list[str] = []
    deadline = time.monotonic() + timeout

    try:
        tty.setcbreak(file_descriptor)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise InputTimedOut

            ready, _, _ = select.select([sys.stdin], [], [], remaining)
            if not ready:
                raise InputTimedOut

            character = sys.stdin.read(1)
            if character in {"\r", "\n"}:
                return "".join(characters)
            if character == "\x03":
                raise KeyboardInterrupt
            if character == "\x04":
                if not characters:
                    raise EOFError
                return "".join(characters)
            if character in {"\x7f", "\b"}:
                if characters:
                    characters.pop()
                    print("\b \b", end="", flush=True)
                continue

            characters.append(character)
            print(character, end="", flush=True)
    finally:
        termios.tcsetattr(file_descriptor, termios.TCSADRAIN, previous_settings)


def _timed_thread_input(timeout: float) -> str:
    # Windows select() cannot wait for redirected console input.
    result: queue.Queue[str | Exception] = queue.Queue(maxsize=1)

    def read_line() -> None:
        try:
            answer = sys.stdin.readline()
            result.put(EOFError() if answer == "" else answer.rstrip("\r\n"))
        except Exception as exc:
            result.put(exc)

    threading.Thread(target=read_line, daemon=True).start()
    try:
        value = result.get(timeout=timeout)
    except queue.Empty as exc:
        raise InputTimedOut from exc
    if isinstance(value, Exception):
        raise value
    return value
