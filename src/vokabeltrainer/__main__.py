"""Entry point so the package can be run with `uv run -m vokabeltrainer <args>`."""

import sys

from vokabeltrainer.cli import main

if __name__ == "__main__":
    sys.exit(main())
