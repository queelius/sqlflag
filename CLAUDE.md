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

sqlflag auto-generates CLIs from SQLite databases. The schema drives everything: tables become subcommands, columns become filter flags, column types determine available operators.

**Two tiers:** Column flags handle single-table AND/OR filtering. Raw SQL (`sql` command) handles JOINs, aggregations, and complex boolean logic.

**Command structure:** Tables are promoted to top-level commands alongside `sql` and `schema`. If a table name collides with a built-in command, it is skipped with a warning (use the `sql` command to query it directly). When mounted via an adapter (e.g., `query_name="db"`), the path is `db repos --stars gt:5`. Direct `click_app` usage: `repos --stars gt:5`.

**Dependency flow:**
```
SqlFlag (cli.py) -- builds Click commands from schema
  ├── SchemaInfo (schema.py) -- introspects tables/columns/types
  ├── QueryEngine (query.py) -- compiles filters to parameterized SQL
  │     └── parse_value (parser.py) -- parses op:value strings
  └── format_rows (formatter.py) -- table/json/csv output
```

**Key design decisions:**

- **Dynamic CLI via Click, not Typer.** Query subcommands use `click.Command(params=[...])` because column flags are determined at runtime from the database schema. Typer's decorator approach requires parameters known at import time. Typer compatibility is maintained through `mount()` which adds Click commands to a Typer app's underlying Click group.

- **sqlite-utils 3.39 does not accept `uri=True`** on `Database.__init__`. Both `SchemaInfo` and `QueryEngine` open raw `sqlite3.connect("file:{path}?mode=ro", uri=True)` connections and pass them to `Database(conn)`.

- **Value parsing rules are ordered:** (1) known operator prefix `op:value`, (2) literal `null`, (3) bare equality. This ensures `not:null` hits the operator path, not the null literal path.

- **Operator set is closed** (7 operators: not, gt, lt, contains, since, before). Unknown prefixes like `foo:bar` are treated as literal equality values. The colon is only special when preceded by a known operator name.

- **All flags are `str` at the Click level** with `multiple=True`. Type coercion (str to int/float) happens in the value parser based on column type from schema.

- **`--any` flag** switches cross-flag conjunction from AND (default) to OR. Conditions within a single flag (e.g., `--stars gt:5 --stars lt:100`) always AND together regardless.

## Spec

Full design spec at `docs/superpowers/specs/2026-03-17-sqlflag-design.md`.
