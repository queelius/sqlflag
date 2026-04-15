# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install in dev mode
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_parser.py -v

# Run a single test
pytest tests/test_parser.py::TestOperators::test_gt -v

# Coverage
pytest tests/ --cov=sqlflag --cov-report=term-missing
```

## Architecture

sqlflag is a **standalone CLI** for ad-hoc querying of SQLite databases. The schema drives everything: tables become subcommands, columns become filter flags, column types determine available operators.

Usage: `sqlflag <db_path> [COMMAND] [ARGS...]` (see `__main__.py`).

**Two tiers:** Column flags handle single-table AND/OR filtering. Raw SQL (`sql` command) handles JOINs, aggregations, and complex boolean logic.

**Command structure:** Tables are promoted to top-level commands alongside `sql` and `schema`. If a table name collides with a built-in command, it is skipped with a warning (use the `sql` command to query it directly).

**Dependency flow:**
```
__main__.main()  --  Click lazy group (SqlFlagGroup) with db_path as @click.argument
  └── SqlFlag (cli.py) -- builds Click commands from schema (lazily, in list/get_command)
        ├── SchemaInfo (schema.py) -- introspects tables/columns/types
        ├── QueryEngine (query.py) -- compiles filters to parameterized SQL
        │     └── parse_value (parser.py) -- parses op:value strings
        └── format_rows (formatter.py) -- table/json/csv output
```

**Key design decisions:**

- **Standalone tool, not an integration library.** Earlier versions shipped click/typer/argparse adapters for mounting into host CLIs; these were removed because the "zero-code integration" promise broke down on non-trivial schemas (each consumer needed `default_columns`, table filters, etc.). Host apps are better served by writing their own query command against their known schema. sqlflag's value is ad-hoc exploration of arbitrary SQLite files.

- **Dynamic CLI via Click lazy group.** The entry point is a `click.Group` subclass (`SqlFlagGroup`) whose `list_commands` and `get_command` build a `SqlFlag` instance on demand from `ctx.params["db_path"]`. This is the standard Click pattern for dynamic CLIs and is what makes shell completion work end-to-end without special casing.

- **sqlite-utils 3.39 does not accept `uri=True`** on `Database.__init__`. Both `SchemaInfo` and `QueryEngine` open raw `sqlite3.connect("file:{path}?mode=ro", uri=True)` connections and pass them to `Database(conn)`.

- **Value parsing rules are ordered:** (1) known operator prefix `op:value`, (2) literal `null`, (3) bare equality. This ensures `not:null` hits the operator path, not the null literal path.

- **Operator set is closed** (7 operators: not, gt, lt, contains, since, before). Unknown prefixes like `foo:bar` are treated as literal equality values. The colon is only special when preceded by a known operator name.

- **All flags are `str` at the Click level** with `multiple=True`. Type coercion (str to int/float) happens in the value parser based on column type from schema.

- **`--any` flag** switches cross-flag conjunction from AND (default) to OR. Conditions within a single flag (e.g., `--stars gt:5 --stars lt:100`) always AND together regardless.

- **Shell completion is schema- and data-aware.** Three custom `ParamType` subclasses in `cli.py`: `ColumnListType` (comma-aware `--columns` completion), `OrderType` (column names for `--order`), and `FilterValueType` (operator-prefix completion plus opt-in distinct-value completion per column). Tier 3 value completion is gated by `SQLFLAG_COMPLETE_VALUES=1` and a cardinality ceiling (`SQLFLAG_VALUE_COMPLETE_MAX`, default 100) to keep TAB latency bounded. All data access in completion is wrapped in try/except: completion must never raise, since a broken completion is strictly better than a crashed shell.

## Spec

Full design spec at `docs/superpowers/specs/2026-03-17-sqlflag-design.md`.
