"""
Making terminal output safe for real documents.

Windows consoles default to the cp1252 code page, which cannot represent most
of what turns up in ordinary notes: arrows, em dashes, curly quotes, accented
names, emoji. Printing such a character raises `UnicodeEncodeError` and kills
the script - a genuinely annoying failure, because the chunking logic was fine
and the crash came from trying to *display* the result.

Since every script in this project prints text pulled from the user's own
documents, every script needs this. Call `enable_utf8_output()` once, before
printing anything.
"""

from __future__ import annotations

import sys


def enable_utf8_output() -> None:
    """Switch stdout and stderr to UTF-8, replacing anything unrepresentable.

    `errors="replace"` is the important half. Even on a terminal that genuinely
    cannot render a character, substituting a placeholder is far better than
    aborting: a slightly wrong glyph still lets you read the chunk, while an
    exception tells you nothing about your data.

    Safe to call more than once, and a no-op on streams that do not support
    reconfiguration, such as a redirected pipe on some platforms.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            # Stream is already closed or detached; nothing useful to do.
            pass
