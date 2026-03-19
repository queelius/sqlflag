"""CSV output format."""

import csv


def write(rows: list[dict], file) -> None:
    if not rows:
        return
    writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
