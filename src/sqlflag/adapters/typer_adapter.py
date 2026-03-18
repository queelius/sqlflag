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
        query_group = root.commands.get("query")
        if query_group:
            click_group.add_command(query_group, name=query_name)
        for cmd_name in ("sql", "schema"):
            cmd = root.commands.get(cmd_name)
            if cmd:
                click_group.add_command(cmd, name=cmd_name)
        return click_group


def mount(app: typer.Typer, sqlflag: SqlFlag, query_name: str = "query") -> click.Group:
    """Mount sqlflag commands into a Typer app.

    Returns the Click group for invocation (since typer.main.get_group()
    creates a new object each call).

    Usage:
        from sqlflag.adapters.typer_adapter import mount
        click_app = mount(my_typer_app, SqlFlag("db.sqlite"))
    """
    return TyperAdapter().mount(app, sqlflag, query_name)
