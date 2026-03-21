"""CLI generation: SqlFlag class with dynamic query commands."""

import warnings

import click
from sqlflag.query import QueryEngine
from sqlflag.schema import SchemaInfo, RESERVED_FLAGS
from sqlflag.formats import available_formats
from sqlflag.formatter import format_rows, detect_format

RESERVED_COMMANDS = frozenset({"sql", "schema"})


class SqlFlag:
    """Auto-generate a CLI from a SQLite database."""

    def __init__(self, db_path: str, tables: list[str] | None = None):
        self._db_path = db_path
        self._tables = tables
        self._schema = SchemaInfo(db_path, tables=tables)
        self._engine = QueryEngine(db_path, schema=self._schema)
        self._click_app = self._build()

    @property
    def click_app(self) -> click.Group:
        return self._click_app

    def run(self):
        self._click_app()

    def _build(self) -> click.Group:
        root = click.Group()

        # table commands at root level
        for table_name in self._schema.queryable_names():
            if table_name in RESERVED_COMMANDS:
                warnings.warn(
                    f"table '{table_name}' skipped "
                    f"(conflicts with built-in command). "
                    f"Use: sql \"SELECT * FROM {table_name}\"",
                    stacklevel=2,
                )
                continue
            cmd = self._make_table_command(table_name)
            root.add_command(cmd, name=table_name)

        # sql command
        engine = self._engine

        @click.command(name="sql")
        @click.argument("query")
        @click.option("--format", "fmt", default=None,
                       type=click.Choice(available_formats()))
        def sql_cmd(query, fmt):
            """Execute raw SQL (read-only)."""
            fmt = fmt or detect_format()
            rows = engine.execute_sql(query)
            format_rows(rows, fmt=fmt)

        root.add_command(sql_cmd)

        # schema command
        self_ref = self

        @click.command(name="schema")
        @click.argument("table", required=False)
        def schema_cmd(table):
            """Inspect database structure."""
            if table:
                self_ref._print_table_schema(table)
            else:
                self_ref._print_schema_overview()

        root.add_command(schema_cmd)

        return root

    def _make_table_command(self, table_name: str) -> click.Command:
        schema = self._schema
        engine = self._engine

        params = [
            click.Option(["--any"], is_flag=True, default=False,
                          help="OR-compose conditions across flags (default is AND)."),
            click.Option(["--order"], multiple=True,
                          help="ORDER BY column. Prefix with - for DESC."),
            click.Option(["--limit"], type=int, default=None,
                          help="Max rows to return."),
            click.Option(["--columns"], default=None,
                          help="Comma-separated columns to display."),
            click.Option(["--format"], default=None,
                          type=click.Choice(available_formats()),
                          help="Output format."),
        ]

        if schema.has_fts(table_name):
            params.append(
                click.Option(["--search"], default=None,
                              help="Full-text search query.")
            )

        col_map = {}
        for col in schema.flaggable_columns(table_name):
            flag_name = f"--{col.name.replace('_', '-')}"
            param_name = col.name.replace("-", "_")
            col_map[param_name] = col.name
            col_type = schema.type_category(table_name, col.name)
            ops = schema.operators_for(table_name, col.name)
            help_text = f"Filter: {col.name} ({col_type}). Ops: {', '.join(ops)}"
            params.append(
                click.Option([flag_name], multiple=True, help=help_text)
            )

        def callback(**kwargs):
            fmt = kwargs.get("format") or detect_format()
            use_any = kwargs.get("any", False)
            order_specs = kwargs.get("order") or []
            limit = kwargs.get("limit")
            columns_str = kwargs.get("columns")
            search_query = kwargs.get("search")
            columns_list = [c.strip() for c in columns_str.split(",")] if columns_str else None

            filters = {}
            for param_name, col_name in col_map.items():
                values = kwargs.get(param_name, ())
                if values:
                    filters[col_name] = list(values)

            rows = engine.query(
                table_name, filters=filters,
                conjunction="any" if use_any else "all",
                order=list(order_specs) if order_specs else None,
                limit=limit, columns=columns_list,
                search=search_query,
            )

            format_rows(rows, fmt=fmt)

        return click.Command(
            name=table_name,
            params=params,
            callback=callback,
            help=f"Query the {table_name} table.",
        )

    def _print_schema_overview(self):
        from rich.console import Console
        from rich.table import Table as RichTable
        console = Console()
        table = RichTable()
        table.add_column("Table")
        table.add_column("Rows", justify="right")
        table.add_column("Columns", justify="right")
        for name in self._schema.table_names():
            cols = self._schema.columns(name)
            count = self._schema.row_count(name)
            table.add_row(name, str(count), str(len(cols)))
        for name in self._schema.view_names():
            cols = self._schema.columns(name)
            count = self._schema.row_count(name)
            table.add_row(f"{name} (view)", str(count), str(len(cols)))
        console.print(table)

    def _print_table_schema(self, table_name: str):
        from rich.console import Console
        from rich.table import Table as RichTable
        console = Console()
        count = self._schema.row_count(table_name)
        console.print(f"Table: {table_name} ({count} rows)\n")
        table = RichTable()
        table.add_column("Column")
        table.add_column("Type")
        table.add_column("Operators")
        reserved = []
        for col in self._schema.columns(table_name):
            cat = self._schema.type_category(table_name, col.name)
            ops = self._schema.operators_for(table_name, col.name)
            if col.name.lower() in RESERVED_FLAGS:
                reserved.append(col.name)
                continue
            table.add_row(col.name, cat, ", ".join(ops))
        console.print(table)
        console.print("\nAll columns support equality (bare value) and IN (repeated flag).")
        if reserved:
            console.print(f"Reserved (use sql): {', '.join(reserved)}")
        fts = self._schema.has_fts(table_name)
        console.print(f"FTS index: {'yes' if fts else 'no'}")

    def mount(self, app, query_name: str = "query"):
        """Mount sqlflag commands into an existing CLI app.

        Convenience method that auto-detects the framework. For explicit
        control, use the adapter modules in sqlflag.adapters instead.
        """
        import argparse

        if isinstance(app, argparse.ArgumentParser):
            from sqlflag.adapters.argparse_adapter import mount
            return mount(app, self, query_name)
        elif isinstance(app, click.Group):
            from sqlflag.adapters.click_adapter import mount
            return mount(app, self, query_name)
        else:
            from sqlflag.adapters.typer_adapter import mount
            return mount(app, self, query_name)
