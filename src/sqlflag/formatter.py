"""Output formatting with pluggable format discovery."""

import sys

from sqlflag.formats import get_writer


def format_rows(rows: list[dict], fmt: str = "table", file=None) -> None:
    if file is None:
        file = sys.stdout
    if not rows:
        return
    writer = get_writer(fmt)
    if writer is None:
        writer = get_writer("json")
    writer(rows, file)


def detect_format() -> str:
    return "table" if sys.stdout.isatty() else "json"
