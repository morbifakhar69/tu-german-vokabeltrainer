"""Typed-answer quiz helpers, including cross-platform timed terminal input."""

from __future__ import annotations

import os
import queue
import random
import sys
import threading
import time
import unicodedata
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
class Question:
    direction: str
    prompt_label: str
    prompt: str
    answer_language: str
    correct_answer: str


def question_for(card: Card, direction: str | None = None) -> Question:
    """Build a question in one of the two study directions."""
    direction = direction if direction is not None else random.choice(DIRECTIONS)

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
    normalized_answer = normalize_answer(answer, question.answer_language)
    accepted = {normalize_answer(question.correct_answer, question.answer_language)}

    if question.answer_language == "de" and card.word_type.casefold() == "noun":
        words = question.correct_answer.strip().split(maxsplit=1)
        if len(words) == 2 and words[0].casefold() in {"der", "die", "das"}:
            accepted.add(normalize_answer(words[1], "de"))
        elif card.gender:
            accepted.add(normalize_answer(f"{card.gender} {question.correct_answer}", "de"))

    return normalized_answer in accepted


def is_quit_command(answer: str) -> bool:
    return answer.strip().casefold() in {"q", "quit"}


def timed_input(prompt: str, timeout: float = FIRST_ATTEMPT_SECONDS) -> str:
    """Read one terminal line before the timeout."""
    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")

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
