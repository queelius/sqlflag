"""Rich table output format."""

from rich.console import Console
from rich.table import Table


def write(rows: list[dict], file) -> None:
    if not rows:
        return
    t = Table()
    columns = list(rows[0].keys())
    for col in columns:
        t.add_column(col)
    for row in rows:
        t.add_row(*[str(v) if v is not None else "" for v in row.values()])
    console = Console(file=file)
    console.print(t)
