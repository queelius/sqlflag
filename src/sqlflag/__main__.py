"""Standalone CLI: `sqlflag <db_path> [subcommand] [args...]`.

Built as a Click lazy group so shell completion works: the db path is a
first-class @click.argument, and subcommands are discovered from the schema
on demand via list_commands / get_command. See docs/superpowers/specs for
design rationale.
"""

import click
from click.shell_completion import BashComplete, FishComplete, ZshComplete

from sqlflag.cli import SqlFlag


_SHELL_COMPLETE_CLASSES = {
    "bash": BashComplete,
    "zsh": ZshComplete,
    "fish": FishComplete,
}


def _emit_completion_source(shell: str) -> None:
    """Print the shell-completion source script for the given shell."""
    cls = _SHELL_COMPLETE_CLASSES[shell]
    instance = cls(main, {}, "sqlflag", "_SQLFLAG_COMPLETE")
    click.echo(instance.source())


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
@click.option(
    "--install-completion",
    type=click.Choice(list(_SHELL_COMPLETE_CLASSES)),
    default=None,
    help="Print shell-completion source for the given shell, then exit. "
         'Install with: eval "$(sqlflag --install-completion bash)"',
)
@click.pass_context
def main(
    ctx: click.Context,
    db_path: str | None,
    install_completion: str | None,
) -> None:
    """sqlflag: auto-generate CLIs from SQLite databases.

    Usage: sqlflag <db_path> [COMMAND] [ARGS...]

    Tables and views become subcommands. Columns become filter flags.
    Use `sqlflag <db_path> schema` to inspect structure.
    Use `sqlflag <db_path> sql "..."` for raw SQL.
    """
    if install_completion is not None:
        _emit_completion_source(install_completion)
        ctx.exit(0)
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)


if __name__ == "__main__":
    main()
