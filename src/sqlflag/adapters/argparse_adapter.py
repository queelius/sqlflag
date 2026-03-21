"""Adapter for mounting SqlFlag into an argparse ArgumentParser."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from sqlflag.cli import SqlFlag


def _find_or_create_subparsers(parser: argparse.ArgumentParser):
    if parser._subparsers is not None:
        for action in parser._subparsers._group_actions:
            if isinstance(action, argparse._SubParsersAction):
                return action
    return parser.add_subparsers(dest="command")


def mount(
    app: argparse.ArgumentParser,
    sqlflag: SqlFlag,
    query_name: str = "query",
) -> argparse.ArgumentParser:
    """Mount all sqlflag commands as a single argparse subparser.

    The subparser delegates to a Click group containing table commands,
    sql, and schema. After parsing, call invoke() to dispatch.

    Usage:
        from sqlflag.adapters.argparse_adapter import mount, invoke

        parser = argparse.ArgumentParser()
        mount(parser, SqlFlag("db.sqlite"), query_name="browse")
        args = parser.parse_args()
        if not invoke(args):
            # not a sqlflag command
            ...

        # CLI: myapp browse repos --language Python
        # CLI: myapp browse schema repos
        # CLI: myapp browse sql "SELECT ..."
    """
    root = sqlflag.click_app

    # Transfer all root commands (table subcommands, sql, schema)
    combined = click.Group(name=query_name, help="Query database tables.")
    for name, cmd in root.commands.items():
        combined.add_command(cmd, name=name)

    # Add a single argparse subparser that delegates to the combined group
    subparsers = _find_or_create_subparsers(app)
    sub = subparsers.add_parser(query_name, help="Query database tables.", add_help=False)
    sub.add_argument("_sqlflag_args", nargs=argparse.REMAINDER)
    sub.set_defaults(_sqlflag_cmd=combined)

    return app


def invoke(parsed: argparse.Namespace) -> bool:
    """Invoke the sqlflag command from a parsed argparse namespace.

    Returns True if a sqlflag command was dispatched, False otherwise.
    """
    cmd = getattr(parsed, "_sqlflag_cmd", None)
    if cmd is None:
        return False
    args = getattr(parsed, "_sqlflag_args", [])
    cmd.main(args, standalone_mode=False)
    return True
