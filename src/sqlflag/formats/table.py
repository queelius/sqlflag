"""Rich table output format."""

from rich.console import Console
from rich.table import Table
from rich.text import Text


def write(rows: list[dict], file) -> None:
    if not rows:
        return
    t = Table()
    columns = list(rows[0].keys())
    for col in columns:
        # Wrap header in Text to bypass Rich markup parsing; a column name
        # like `[/foo]` would otherwise be misinterpreted as a closing tag.
        t.add_column(Text(col))
    for row in rows:
        # Wrap each cell value in Text so chat-format tokens like [INST] /
        # [/INST] and other bracket-containing data render literally instead
        # of being parsed as Rich markup (which would raise MarkupError).
        t.add_row(*[
            Text(str(v)) if v is not None else Text("")
            for v in row.values()
        ])
    console = Console(file=file)
    console.print(t)
