"""CLI generation: SqlFlag class with dynamic query commands."""

import os
import warnings

import click
from click.shell_completion import CompletionItem
from sqlflag.query import QueryEngine
from sqlflag.schema import SchemaInfo, RESERVED_FLAGS
from sqlflag.formats import available_formats
from sqlflag.formatter import format_rows, detect_format

RESERVED_COMMANDS = frozenset({"sql", "schema"})
VALUE_COMPLETE_DEFAULT_MAX = 100


class ColumnListType(click.ParamType):
    """Comma-separated column list for --columns.

    Shell-complete: offers remaining columns, comma-aware so that typing
    `name,<TAB>` returns `name,language`, `name,stars`, etc. (not `name,name`).
    """

    name = "column_list"

    def __init__(self, columns: list[str]):
        self._columns = columns

    def convert(self, value, param, ctx):
        return value  # no runtime conversion; handled downstream

    def shell_complete(self, ctx, param, incomplete):
        parts = incomplete.split(",")
        already = {p.strip() for p in parts[:-1] if p.strip()}
        prefix = ",".join(parts[:-1])
        if prefix:
            prefix += ","
        current = parts[-1]
        return [
            CompletionItem(prefix + col)
            for col in self._columns
            if col not in already and col.startswith(current)
        ]


class OrderType(click.ParamType):
    """Column name for ORDER BY with optional `-` prefix for DESC.

    Shell-complete: offers ascending columns by default; when the incomplete
    starts with `-`, offers `-column` candidates for DESC. Note: Click/bash
    treat `-<TAB>` at a value position as a new option flag, so tab-completing
    the `-` prefix does not route through this method in practice. Users type
    `--order -column` manually. Unit tests still exercise the `-` path in
    case Click's dispatch changes.
    """

    name = "order_spec"

    def __init__(self, columns: list[str]):
        self._columns = columns

    def convert(self, value, param, ctx):
        return value

    def shell_complete(self, ctx, param, incomplete):
        if incomplete.startswith("-"):
            stem = incomplete[1:]
            return [
                CompletionItem(f"-{col}")
                for col in self._columns
                if col.startswith(stem)
            ]
        return [
            CompletionItem(col)
            for col in self._columns
            if col.startswith(incomplete)
        ]


class FilterValueType(click.ParamType):
    """Per-column filter value: accepts `[op:]value`.

    Shell-complete offers:
    - Operator prefixes for this column's type category (Tier 2, always on).
    - The reserved literal `null` (always on).
    - Distinct data values (Tier 3, opt-in via SQLFLAG_COMPLETE_VALUES=1).

    Tier 3 is bounded by SQLFLAG_VALUE_COMPLETE_MAX (default 100). If the
    column has more distinct values than the ceiling, value completion is
    skipped and only operators are returned. Completion never raises: data
    errors degrade silently so a broken DB cannot crash the user's shell.
    """

    name = "filter_value"

    def __init__(
        self,
        operators: list[str],
        table_name: str | None = None,
        column_name: str | None = None,
        engine: QueryEngine | None = None,
    ):
        self._operators = operators
        self._table = table_name
        self._column = column_name
        self._engine = engine

    def convert(self, value, param, ctx):
        return value  # parsing happens in the query engine

    def shell_complete(self, ctx, param, incomplete):
        items = []
        # Tier 2: operator prefixes
        for op in self._operators:
            prefix = f"{op}:"
            if prefix.startswith(incomplete):
                items.append(CompletionItem(prefix))
        if "null".startswith(incomplete):
            items.append(CompletionItem("null"))
        # Tier 3: data-aware value completion
        if self._should_complete_values(incomplete):
            for value in self._safe_distinct_values():
                if value.startswith(incomplete):
                    items.append(CompletionItem(value))
        return items

    def _should_complete_values(self, incomplete: str) -> bool:
        if not os.environ.get("SQLFLAG_COMPLETE_VALUES"):
            return False
        if self._engine is None or self._table is None or self._column is None:
            return False
        # Suppress value completion once user has committed to an operator prefix
        for op in self._operators:
            if incomplete.startswith(f"{op}:"):
                return False
        return True

    def _safe_distinct_values(self) -> list[str]:
        try:
            max_card = int(os.environ.get(
                "SQLFLAG_VALUE_COMPLETE_MAX", VALUE_COMPLETE_DEFAULT_MAX
            ))
            values = self._engine.distinct_values_bounded(
                self._table, self._column, max_card
            )
            return values or []
        except Exception:
            return []


class SqlFlag:
    """Auto-generate a CLI from a SQLite database."""

    def __init__(
        self,
        db_path: str,
        tables: list[str] | None = None,
        default_columns: dict[str, list[str]] | None = None,
    ):
        self._db_path = db_path
        self._tables = tables
        self._default_columns = default_columns or {}
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
        table_default_columns = self._default_columns.get(table_name)
        all_column_names = [c.name for c in schema.columns(table_name)]

        params = [
            click.Option(["--any"], is_flag=True, default=False,
                          help="OR-compose conditions across flags (default is AND)."),
            click.Option(["--order"], multiple=True,
                          type=OrderType(all_column_names),
                          help="ORDER BY column. Prefix with - for DESC."),
            click.Option(["--limit"], type=int, default=None,
                          help="Max rows to return."),
            click.Option(["--columns"], default=None,
                          type=ColumnListType(all_column_names),
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
                click.Option(
                    [flag_name],
                    multiple=True,
                    type=FilterValueType(
                        operators=ops,
                        table_name=table_name,
                        column_name=col.name,
                        engine=engine,
                    ),
                    help=help_text,
                )
            )

        def callback(**kwargs):
            fmt = kwargs.get("format") or detect_format()
            use_any = kwargs.get("any", False)
            order_specs = kwargs.get("order") or []
            limit = kwargs.get("limit")
            columns_str = kwargs.get("columns")
            search_query = kwargs.get("search")
            columns_list = (
                [c.strip() for c in columns_str.split(",")]
                if columns_str
                else table_default_columns
            )

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
