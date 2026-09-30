# TU German Vokabeltrainer

A small command-line spaced-repetition flashcard app for learning German
vocabulary. Final project for my Python programming course at TU Dortmund.

## Why

A lot of international students struggle with building up German vocabulary
fast enough - myself included. Most flashcard apps are either overkill
(Anki) or don't tell you *what* you're actually struggling with. This is a
small, personal version: a CSV of words in, spaced-repetition scheduling,
filtering by topic, desktop reminders, and a couple of stats/plots to see
how you're doing.

## Features

- **Spaced repetition** using a simplified SM-2 algorithm (the classic
  SuperMemo scheduling algorithm) - correct first attempts come back after
  longer and longer intervals, while wrong or timed-out answers come back
  tomorrow.
- **Typed-answer flashcards** - cards go in either direction (German to
  English or English to German). A visible 10-second countdown warns when
  time is up, but you can still finish typing; late answers are shown and
  recorded without earning a point.
- **Filter by category or shuffle the study order** - 13 topics bundled
  (greetings, numbers, family, food, time, travel, university life, verbs,
  adjectives, colors, shopping, weather, directions).
- **Grammar hints** - nouns show their article (`der`/`die`/`das`), and
  verbs that *always* take a specific case show it, e.g. `helfen (+Dativ)`
  or `sehen (+Akkusativ)`.
- **Progress persists** in a local SQLite database, separate from the
  vocabulary CSV, so you can extend the word list later without losing
  what you've already learned.
- **`watch` mode** - a foreground command that periodically checks for due
  cards and fires a native desktop notification (macOS via `osascript`,
  Windows via `plyer`), so you get reminded to study without needing a
  background service.
- **Stats & plots** - accuracy overall and per category, plus a saved PNG
  showing reviews/accuracy over time (see [`plots/review_stats.png`](plots/review_stats.png),
  generated from a simulated two-week study history).

## Installation

Requires Python >= 3.10 and [uv](https://astral.sh/uv). The project is an
installable `pyproject.toml` package; no `setup.py` is needed.

```bash
git clone https://github.com/morbifakhar69/tu-german-vokabeltrainer.git
cd tu-german-vokabeltrainer
uv venv
source .venv/bin/activate    # on Windows: .venv\Scripts\activate
uv pip install -e .
```

Verify the installation by opening the command-line help:

```bash
uv run -m vokabeltrainer --help
```

On Windows, install the optional notification backend too:

```bash
uv pip install -e ".[win]"
```

Optional extras may need network access the first time so uv can cache their
platform-specific packages.

## Usage

Everything runs through the package's `__main__.py`:

```bash
uv run -m vokabeltrainer <command> [options]
```

(a `vokabeltrainer` console script is also installed, so `vokabeltrainer <command>`
works the same way once the venv is activated)

Use these exact help commands to see every current command and option:

```bash
uv run -m vokabeltrainer --help
uv run -m vokabeltrainer study --help
```

### List categories

```bash
uv run -m vokabeltrainer categories
```

### See what's due today

```bash
uv run -m vokabeltrainer due
uv run -m vokabeltrainer due --category verbs
```

### Study

```bash
uv run -m vokabeltrainer study                       # due cards, in order
uv run -m vokabeltrainer study --category food        # only one topic
uv run -m vokabeltrainer study --random --questions 15 # shuffled, 15 questions
uv run -m vokabeltrainer study --all                  # ignore due dates (good for a first run)
```

Each session asks up to 10 questions by default (`--questions COUNT` changes
that, and `--limit` remains an alias). Every card randomly shows either English
or German and asks you to type the translation. A visible 10-second countdown
warns when time is up, but it does not stop you from finishing your answer. The
correct answer is always shown. If the first answer is wrong or late, you get
one untimed retry for practice. That retry does not change the grade: only the
first answer is used for scheduling.

Checking is case-insensitive, ignores extra spaces, and accepts spellings such
as `ue` for `ü`. For German nouns, the article can be left out, but a wrong
article is not accepted. Type `q` or `quit` to stop early. The final summary
shows correct/reviewed answers, accuracy, and the number of late answers.

Example session (the direction is selected randomly):

```text
Studying 2 typed-answer card(s). You have 10 seconds for each first attempt.

English: dog
  Your answer (q to quit): [8s remaining] der Hund
  Correct!
  Correct answer: der Hund
  Session score: 1/1 (100%)

German: helfen (+Dativ)
  Your answer (q to quit): [time's up - answer will be marked late] to help
  Time's up - that answer is recorded as late.
  Your answer matches, but late answers do not score.
  Correct answer: to help
  Retry (untimed, q to quit): to help
  Retry correct - good practice.
  Session score: 1/2 (50%)

Session done - 1/2 correct across 2 reviewed card(s) (50%). 1 late answer(s).
```

### Study options

| option | effect |
|--------|--------|
| `--questions COUNT` | Ask at most `COUNT` questions; defaults to `10` |
| `--limit COUNT` | Backwards-compatible alias for `--questions` |
| `--category NAME` | Study only one category |
| `--random` | Shuffle card order; prompt direction is randomized regardless |
| `--all` | Include cards that are not due yet |
| `--dataset PATH` | Read another vocabulary CSV |
| `--db PATH` | Store progress in another SQLite database |

### Get reminded periodically

```bash
uv run -m vokabeltrainer watch --interval 30   # check every 30 minutes
```

Stays running in the foreground and sends a desktop notification whenever
cards are due. Stop with `Ctrl+C`.

### Stats & plot

```bash
uv run -m vokabeltrainer stats
```

Prints overall + per-category accuracy and a suggestion for which category
to focus on next, and saves a plot to `plots/review_stats.png`.

### Add a word without editing the CSV by hand

```bash
cp src/vokabeltrainer/data/vocabulary_demo.csv my-vocabulary.csv
uv run -m vokabeltrainer add-word "das Fenster" window home \
  --word-type noun --gender das --dataset my-vocabulary.csv
```

The example first makes a reusable personal copy, then appends a row to it.
Without `--dataset`, `add-word` uses the bundled demo set. This is handy for
quickly adding a word you just looked up without opening the CSV in an editor.

### Using your own vocabulary list

All commands accept `--dataset path/to/your.csv` to use a different word
list instead of the bundled demo set. The CSV needs these columns:

| column        | required | meaning                                              |
|---------------|----------|-------------------------------------------------------|
| `german`      | yes      | the German word or phrase                             |
| `english`     | yes      | the English translation                                |
| `category`    | yes      | topic, used for `--category` filtering                |
| `word_type`   | no       | noun / verb / adjective / phrase / number / ...        |
| `gender`      | no       | `der` / `die` / `das`, for nouns                       |
| `verb_case`   | no       | `akkusativ` / `dativ`, only if the verb *always* takes it |
| `example_de`  | no       | example sentence in German                             |
| `example_en`  | no       | example sentence in English                            |

The bundled beginner dataset
([`src/vokabeltrainer/data/vocabulary_demo.csv`](src/vokabeltrainer/data/vocabulary_demo.csv))
has 166 hand-picked words across the 13 topics above. It is hand-curated rather
than scraped because ready-made lists rarely combine translations, topics,
noun gender, and verb case. Since card progress is keyed by a hash of the word
and category, you can reuse or extend a CSV later without losing progress on
unchanged cards.

### Python API

The typed `FlashCard`, `VocabularyBank`, and `QuizSession` objects are
available directly from the package:

```python
import random
import time
from pathlib import Path

from vokabeltrainer import FlashCard, QuizSession, VocabularyBank

vocabulary = VocabularyBank.beginner()  # bundled 166-card dataset
first_card: FlashCard = vocabulary[0]
print(first_card.german, first_card.english)

imported = VocabularyBank.from_csv(Path("my-vocabulary.csv"))
session = QuizSession(imported[:10], rng=random.Random(42))

while not session.finished:
    question = session.current_question
    assert question is not None
    print(question.prompt_label, question.prompt)
    started_at = time.monotonic()
    answer = input("> ")
    session.submit_answer(answer, elapsed_seconds=time.monotonic() - started_at)

results = session.final_results()
print(f"{results.score}/{results.reviewed} ({results.accuracy:.0%})")
```

`VocabularyBank.from_csv(path)` uses the same validation as the CLI. The
original `Card` name remains an alias for backwards compatibility.
`QuizSession` provides randomized German-to-English and English-to-German
questions, answer checking, a running score, late-answer tracking, and final
results. Pass `random.Random(seed)` as `rng` for a repeatable question sequence.

## Package architecture

The CLI is a thin adapter around reusable package modules: `dataset.py` builds
typed cards, `quiz.py` grades one session, `scheduler.py` updates due dates,
`storage.py` persists progress, and `stats.py` summarizes review history.

```
src/vokabeltrainer/
    __main__.py     entry point (`uv run -m vokabeltrainer`)
    cli.py          argparse subcommands
    quiz.py         QuizSession, answer checks, and cross-platform timed input
    models.py       FlashCard / ReviewResult data classes
    scheduler.py     the SM-2 spaced-repetition algorithm
    dataset.py       CSV loading/validation
    storage.py       SQLite-backed progress persistence
    stats.py         accuracy summaries + matplotlib plot
    notifier.py      cross-platform desktop notifications
    data/            bundled demo vocabulary CSV
tests/               pytest test suite
notebooks/           demo.ipynb - same functionality via the Python API
plots/               example generated output
```

## Notebook

[`notebooks/demo.ipynb`](notebooks/demo.ipynb) shows the same functionality
through the package's Python API instead of the CLI - loading cards, running
a few reviews through the scheduler directly, and generating a stats plot.

```bash
uv pip install -e ".[notebook]"
jupyter notebook notebooks/demo.ipynb
```

## Development

```bash
uv pip install -e ".[dev]"
uv run --frozen pytest -q
uv run --frozen ruff check .
```

After the dependencies have been cached once, the editable development install
also works without network access:

```bash
uv pip install --offline -e ".[dev]"
```

## License

MIT, see [LICENSE](LICENSE).
