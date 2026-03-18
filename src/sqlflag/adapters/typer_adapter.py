"""Adapter for mounting SqlFlag into a Typer app."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click
import typer
import typer.main
from sqlflag.adapters import Adapter

if TYPE_CHECKING:
    from sqlflag.cli import SqlFlag


class TyperAdapter(Adapter):
    def mount(self, app: typer.Typer, sqlflag: SqlFlag, query_name: str = "query") -> click.Group:
        click_group = typer.main.get_group(app)
        root = sqlflag.click_app
        group = click.Group(name=query_name, help="Query database tables.")

        # Flatten table commands from the query subgroup
        query_group = root.commands.get("query")
        if query_group:
            for name, cmd in query_group.commands.items():
                group.add_command(cmd, name=name)

        # Add sql and schema alongside table commands
        for cmd_name in ("sql", "schema"):
            cmd = root.commands.get(cmd_name)
            if cmd:
                group.add_command(cmd, name=cmd_name)

        click_group.add_command(group)
        return click_group


def mount(app: typer.Typer, sqlflag: SqlFlag, query_name: str = "query") -> click.Group:
    """Mount all sqlflag commands as a single group in a Typer app.

    Returns the Click group for invocation (since typer.main.get_group()
    creates a new object each call).

    Usage:
        from sqlflag.adapters.typer_adapter import mount
        click_app = mount(my_typer_app, SqlFlag("db.sqlite"), query_name="browse")
    """
    return TyperAdapter().mount(app, sqlflag, query_name)
