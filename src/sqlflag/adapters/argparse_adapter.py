"""Adapter for mounting SqlFlag into an argparse ArgumentParser."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

import click
from sqlflag.adapters import Adapter

if TYPE_CHECKING:
    from sqlflag.cli import SqlFlag


class ArgparseAdapter(Adapter):
    def mount(
        self,
        app: argparse.ArgumentParser,
        sqlflag: SqlFlag,
        query_name: str = "query",
    ) -> argparse.ArgumentParser:
        root = sqlflag.click_app
        subparsers = self._find_or_create_subparsers(app)

        for name in (query_name, "sql", "schema"):
            src_name = "query" if name == query_name else name
            cmd = root.commands.get(src_name)
            if cmd:
                sub = subparsers.add_parser(name, help=cmd.help, add_help=False)
                sub.add_argument("_sqlflag_args", nargs=argparse.REMAINDER)
                sub.set_defaults(_sqlflag_cmd=cmd)

        return app

    @staticmethod
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
    """Mount sqlflag commands into an argparse ArgumentParser.

    After parsing, call invoke() with the parsed namespace
    to dispatch sqlflag commands.

    Usage:
        from sqlflag.adapters.argparse_adapter import mount, invoke

        parser = argparse.ArgumentParser()
        mount(parser, SqlFlag("db.sqlite"))
        args = parser.parse_args()
        if not invoke(args):
            # not a sqlflag command, handle normally
            ...
    """
    return ArgparseAdapter().mount(app, sqlflag, query_name)


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
