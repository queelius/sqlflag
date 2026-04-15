"""Standalone CLI: `sqlflag <db_path> [subcommand] [args...]`.

Built as a Click lazy group so shell completion works: the db path is a
first-class @click.argument, and subcommands are discovered from the schema
on demand via list_commands / get_command. See docs/superpowers/specs for
design rationale.
"""

import click

from sqlflag.cli import SqlFlag


class SqlFlagGroup(click.Group):
    """Click group whose subcommands are derived from a SQLite database at runtime."""

    def _sqlflag(self, ctx: click.Context) -> SqlFlag | None:
        cached = ctx.meta.get("sqlflag.instance")
        if cached is not None:
            return cached
        db_path = ctx.params.get("db_path")
        if not db_path:
            return None
        sf = SqlFlag(db_path)
        ctx.meta["sqlflag.instance"] = sf
        return sf

    def list_commands(self, ctx: click.Context) -> list[str]:
        sf = self._sqlflag(ctx)
        if sf is None:
            return []
        return sorted(sf.click_app.commands)

    def get_command(self, ctx: click.Context, name: str) -> click.Command | None:
        sf = self._sqlflag(ctx)
        if sf is None:
            return None
        return sf.click_app.commands.get(name)


@click.group(
    cls=SqlFlagGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
@click.argument(
    "db_path",
    type=click.Path(exists=True, dir_okay=False),
    required=False,
)
@click.pass_context
def main(ctx: click.Context, db_path: str | None) -> None:
    """sqlflag: auto-generate CLIs from SQLite databases.

    Usage: sqlflag <db_path> [COMMAND] [ARGS...]

    Tables and views become subcommands. Columns become filter flags.
    Use `sqlflag <db_path> schema` to inspect structure.
    Use `sqlflag <db_path> sql "..."` for raw SQL.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)


if __name__ == "__main__":
    main()
