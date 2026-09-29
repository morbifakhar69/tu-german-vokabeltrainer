"""Cross-platform desktop notifications (macOS + Windows, best-effort elsewhere).

Kept intentionally small - just enough for the `watch` command to nudge you
when cards are due. On macOS we shell out to `osascript`, which ships with
the OS, so no extra dependency is needed. On Windows we use the optional
`plyer` package (install with `uv pip install -e ".[win]"`).
"""

from __future__ import annotations

import shutil
import subprocess
import sys


def notify(title: str, message: str) -> None:
    """Best-effort desktop notification. Falls back to printing if nothing works.

    Notifications are a nice-to-have for this app, never something worth
    crashing over, so any failure here is swallowed and we just print
    instead.
    """
    try:
        if sys.platform == "darwin":
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            return

        if sys.platform == "win32":
            from plyer import notification  # optional dependency, see pyproject.toml [win]

            notification.notify(title=title, message=message, timeout=8)
            return

        if shutil.which("notify-send"):  # linux - not officially required, but nice to have
            subprocess.run(["notify-send", title, message], check=True)
            return
    except Exception:
        pass

    print(f"[{title}] {message}")
