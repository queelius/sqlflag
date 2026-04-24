"""Rich table output format."""

from rich.console import Console
from rich.table import Table
from rich.text import Text


def write(rows: list[dict], file) -> None:
    if not rows:
        return
    # Wrap headers and cells in Text to bypass Rich markup parsing: values
    # containing brackets (e.g. [INST], [/foo]) would otherwise be parsed as
    # markup tags and raise MarkupError.
    t = Table()
    for col in rows[0].keys():
        t.add_column(Text(col))
    for row in rows:
        t.add_row(*[Text("" if v is None else str(v)) for v in row.values()])
    Console(file=file).print(t)
