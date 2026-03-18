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
        query_group = root.commands.get("query")
        if query_group:
            app.add_command(query_group, name=query_name)
        for cmd_name in ("sql", "schema"):
            cmd = root.commands.get(cmd_name)
            if cmd:
                app.add_command(cmd, name=cmd_name)
        return app


def mount(app: click.Group, sqlflag: SqlFlag, query_name: str = "query") -> click.Group:
    """Mount sqlflag commands into a Click Group.

    Usage:
        from sqlflag.adapters.click_adapter import mount
        mount(my_click_group, SqlFlag("db.sqlite"))
    """
    return ClickAdapter().mount(app, sqlflag, query_name)
