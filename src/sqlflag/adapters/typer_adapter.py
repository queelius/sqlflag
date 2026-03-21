"""Adapter for mounting SqlFlag into a Typer app."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click
import typer
import typer.main

if TYPE_CHECKING:
    from sqlflag.cli import SqlFlag


def mount(app: typer.Typer, sqlflag: SqlFlag, query_name: str = "query") -> click.Group:
    """Mount all sqlflag commands as a single group in a Typer app.

    Returns the Click group for invocation (since typer.main.get_group()
    creates a new object each call).

    Usage:
        from sqlflag.adapters.typer_adapter import mount
        click_app = mount(my_typer_app, SqlFlag("db.sqlite"), query_name="browse")
    """
    click_group = typer.main.get_group(app)
    root = sqlflag.click_app
    group = click.Group(name=query_name, help="Query database tables.")
    for name, cmd in root.commands.items():
        group.add_command(cmd, name=name)
    click_group.add_command(group)
    return click_group
