"""JSONL output format."""

import json


def write(rows: list[dict], file) -> None:
    for row in rows:
        file.write(json.dumps(row, default=str) + "\n")
