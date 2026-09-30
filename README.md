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
  English or English to German). The first answer has a 10-second limit and
  the app grades it automatically.
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

Requires Python >= 3.10 and [uv](https://astral.sh/uv).

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

## Usage

Everything runs through the package's `__main__.py`:

```bash
uv run -m vokabeltrainer <command> [options]
```

(a `vokabeltrainer` console script is also installed, so `vokabeltrainer <command>`
works the same way once the venv is activated)

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
uv run -m vokabeltrainer study --random --limit 15    # shuffled, capped
uv run -m vokabeltrainer study --all                  # ignore due dates (good for a first run)
```

Each card shows either English or German and asks you to type the translation.
You get 10 seconds for the first try. The correct answer is always shown. If the
first answer is wrong or too late, you get one untimed retry for practice. That
retry does not change the grade: only the first answer is used for scheduling.

Checking is case-insensitive, ignores extra spaces, and accepts spellings such
as `ue` for `ü`. For German nouns, the article can be left out, but a wrong
article is not accepted. Type `q` or `quit` to stop early.

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
uv run -m vokabeltrainer add-word "das Fenster" window home --word-type noun --gender das
```

Appends a row to the dataset (bundled demo set by default, or whatever
`--dataset` you pass). Handy for quickly adding a word you just looked up
without opening the CSV in an editor.

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

The bundled dataset ([`src/vokabeltrainer/data/vocabulary_demo.csv`](src/vokabeltrainer/data/vocabulary_demo.csv))
has 166 hand-picked words across the 13 topics above. I checked Kaggle and
GitHub for a ready-made dataset combining translations + categories + verb
case info and didn't find one, so this is hand-curated rather than scraped.
Since card progress is keyed by a hash of the word + category, you can drop
in a bigger CSV (e.g. a 3000-word list) later using the same columns
without losing progress on the words that are already there.

### Python API

The typed `FlashCard` and `VocabularyBank` objects are available directly from
the package:

```python
from vokabeltrainer import FlashCard, VocabularyBank

vocabulary = VocabularyBank.beginner()
first_card: FlashCard = vocabulary[0]
print(first_card.german, first_card.english)
```

`VocabularyBank.from_csv(path)` loads another file using the same validated
CSV format. The original `Card` name remains available as an alias for
backwards compatibility.

## Project layout

```
src/vokabeltrainer/
    __main__.py     entry point (`uv run -m vokabeltrainer`)
    cli.py          argparse subcommands
    quiz.py         typed-answer checks and cross-platform timed input
    models.py        Card / ReviewResult data classes
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
pytest
ruff check .
```

## License

MIT, see [LICENSE](LICENSE).
