"""Output formatting: table, json, csv."""

import csv
import json
import sys
from rich.console import Console
from rich.table import Table


def format_rows(rows: list[dict], fmt: str = "table", file=None) -> None:
    if file is None:
        file = sys.stdout
    if not rows:
        return
    if fmt == "json":
        _write_json(rows, file)
    elif fmt == "csv":
        _write_csv(rows, file)
    elif fmt == "table":
        _write_table(rows, file)
    else:
        _write_json(rows, file)


def _write_json(rows: list[dict], file) -> None:
    for row in rows:
        file.write(json.dumps(row, default=str) + "\n")


def _write_csv(rows: list[dict], file) -> None:
    if not rows:
        return
    writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)


def _write_table(rows: list[dict], file) -> None:
    if not rows:
        return
    table = Table()
    columns = list(rows[0].keys())
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*[str(v) if v is not None else "" for v in row.values()])
    console = Console(file=file)
    console.print(table)


def detect_format() -> str:
    return "table" if sys.stdout.isatty() else "json"
