"""Adapter for mounting SqlFlag into a Click Group."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click
from sqlflag.adapters import Adapter

if TYPE_CHECKING:
    from sqlflag.cli import SqlFlag


class ClickAdapter(Adapter):
    def mount(self, app: click.Group, sqlflag: SqlFlag, query_name: str = "query") -> click.Group:
        root = sqlflag.click_app
        group = click.Group(name=query_name, help="Query database tables.")
        for name, cmd in root.commands.items():
            group.add_command(cmd, name=name)
        app.add_command(group)
        return app


def mount(app: click.Group, sqlflag: SqlFlag, query_name: str = "query") -> click.Group:
    """Mount all sqlflag commands as a single group in a Click app.

    Creates a command group (default name "query") containing table
    subcommands, sql, and schema -- all namespaced to avoid conflicts.

    Usage:
        from sqlflag.adapters.click_adapter import mount
        mount(my_click_group, SqlFlag("db.sqlite"), query_name="browse")
        # my_click_group browse table repos --language Python
        # my_click_group browse schema repos
        # my_click_group browse sql "SELECT ..."
    """
    return ClickAdapter().mount(app, sqlflag, query_name)
