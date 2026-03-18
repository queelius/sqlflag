# sqlflag Design Spec

**Date**: 2026-03-17
**Status**: Draft
**PyPI name**: `sqlflag`

## Problem

SQL-backed CLIs and MCP servers repeatedly reimplement the same layers: schema introspection, flag-to-SQL translation, output formatting, and connection management. Each project (repoindex, chartfold, memex, crier, jot) solves this differently, with 200-700 lines of per-project query/CLI boilerplate.

## Solution

A Python library that auto-generates a user-friendly CLI from any SQLite database. Tables become subcommands. Columns become filter flags. A small, closed operator syntax handles non-equality filters. Raw SQL provides the escape hatch.

## Design Principles

- **Uniformity**: One pattern for filtering: `--col [op:]value`. No alternative syntax.
- **Simplicity**: Two tiers only. Flags and raw SQL. No intermediate DSL, no `--where`.
- **Just enough power**: Flags cover single-table filtering with AND/OR composition. SQL covers everything else (JOINs, aggregations, subqueries, nested boolean logic).
- **Derive from structure**: The schema IS the CLI spec. Adding a column to the database automatically creates a flag. No parallel mappings to maintain.

## Architecture

```
┌─────────────────────────────────────┐
│  Your project CLI                   │
│  (optional project-specific cmds)   │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  sqlflag                            │
│                                     │
│  Schema introspection (sqlite-utils)│
│  Value parser (op:value → SQL)      │
│  Typer command generation           │
│  Output formatting (table/json/csv) │
└──────────────┬──────────────────────┘
               │
         ┌─────▼─────┐
         │  SQLite    │
         └───────────┘
```

### Dependencies

- **sqlite-utils**: Schema introspection (`table.columns`, `table.rows_where()`), query execution, FTS support (`table.search()`), connection management. Used as a library, not its CLI.
- **typer**: CLI framework (dynamic command generation)
- **rich**: Table output formatting (comes with typer)

No custom SQL parser. No sqlglot. sqlite-utils and SQLite itself handle query execution and error reporting.

## Two Tiers

### Tier 1: Column Flags

Table queries live under a `query` subcommand group. Each table/view is a subcommand under `query`.

Every table/view subcommand gets:

- One `--colname` flag per column (type derived from schema, `multiple=True`)
- Reserved flags for ordering, output control, and conjunction mode
- Optional `--search` flag if the table has an FTS index

```bash
myapp query repos --language python --stars gt:50 --order -stars --limit 10
myapp query events --created-at since:30d --format json
myapp query repos --language python --language go
myapp query repos --language python --stars gt:50 --any
```

By default, all conditions are AND-composed (`--all`). Pass `--any` to OR-compose instead.

### Tier 2: Raw SQL

```bash
myapp sql "SELECT r.name, COUNT(e.id) FROM repos r JOIN events e ON ..."
```

Read-only enforcement. Full SQL power for JOINs, nested boolean logic, aggregations, subqueries.

## Value Syntax

Every column flag accepts `multiple=True`. Each value is parsed as `[op:]value`.

### Parsing Rules

Applied in order:

1. If value matches `KNOWN_OP:REST` where `KNOWN_OP` is in the closed operator set, apply that operator to REST
2. If value is the literal `null`, produce `IS NULL`
3. Otherwise, treat the entire string as a literal for equality (`=`)

Rule 1 means a value like `foo:bar` where `foo` is not a known operator is treated as the literal string `"foo:bar"` for equality. The colon is only special when preceded by an operator name from the closed set.

The literal string `"null"` cannot be queried via flags. Use `sql` for this rare case.

### Combining Multiple Values on the Same Flag

- All bare values collect into `= val` (single) or `IN (val1, val2, ...)` (multiple)
- Each operator-prefixed value becomes its own condition
- Conditions within a flag AND together (regardless of `--any`/`--all` mode)
- Conditions across different flags are joined by the conjunction mode (AND by default, OR with `--any`)

Mixing bare and operator-prefixed values on the same flag is allowed but discouraged. The system produces valid SQL; contradictory logic (e.g., `--stars 10 --stars gt:50`) is user error.

Examples:

```bash
--language python                       # language = 'python'
--language python --language go         # language IN ('python', 'go')
--stars gt:5 --stars lt:100             # stars > 5 AND stars < 100
--stars gt:5 --language python          # stars > 5 AND language = 'python'
--stars gt:5 --language python --any    # stars > 5 OR language = 'python'
```

### Operator Table

| Prefix | SQL | Notes |
|--------|-----|-------|
| *(bare)* | `=` / `IN` | Default. Multiple bare values produce IN. |
| `not:` | `!=` | `not:null` produces `IS NOT NULL`. |
| `gt:` | `>` | |
| `lt:` | `<` | |
| `contains:` | `LIKE '%val%'` | Substring match. User does not supply wildcards. |
| `since:` | `>=` | Relative dates (`30d`, `4w`, `6h`, `3mo`, `1y`) or absolute ISO 8601. |
| `before:` | `<` | Same date parsing as `since:`. |

7 operators + bare default. Closed set.

### Relative Date Format

Used with `since:` and `before:` operators:

| Unit | Meaning | Example |
|------|---------|---------|
| `min` | minutes | `30min` |
| `h` | hours | `6h` |
| `d` | days | `30d` |
| `w` | weeks | `4w` |
| `mo` | months | `3mo` |
| `y` | years | `1y` |

Absolute dates (ISO 8601) are passed through as-is. Relative dates are computed from the current time to an ISO 8601 string. This works correctly for date/datetime columns stored in ISO 8601 format (SQLite convention).

## Reserved Flags

Every table subcommand includes these. Column flags cannot shadow them.

| Flag | Purpose | Notes |
|------|---------|-------|
| `--all` | AND-compose all conditions | Default behavior. Explicit flag for clarity. |
| `--any` | OR-compose conditions across flags | Conditions within a single flag still AND together. |
| `--order COL` | ORDER BY | `multiple=True`. Prefix with `-` for descending: `--order -stars`. |
| `--limit N` | LIMIT | |
| `--columns A,B,C` | SELECT only these columns | Comma-separated column names. |
| `--format F` | Output format: `table`, `json`, `csv` | Auto-detects: `table` for TTY, `json` for pipe. |
| `--search TEXT` | Full-text search | Only present if table has FTS index. ANDed with column filters. `--order` overrides FTS ranking. |

**Reserved names**: `all`, `any`, `order`, `limit`, `columns`, `format`, `search`, `help`. A table column with a reserved name is reachable only via `sql`.

## Auto-Generated Commands

### Command Structure

Top-level commands:

```
myapp query <TABLE> [flags]    # Query a table with column flags
myapp sql QUERY                # Execute raw SQL (read-only)
myapp schema [TABLE]           # Inspect database structure
```

Under `query`, one subcommand per table and per view. Views are treated identically to tables.

```
myapp query repos [--col op:val ...] [--order COL] [--limit N] [--format F]
myapp query events [--col op:val ...] [--order COL] [--limit N] [--format F]
myapp query active_repos [...]   # from CREATE VIEW active_repos AS ...
```

The `query` subcommand name is configurable when mounting into an existing CLI. Default is `query`.

### Table Allowlist

By default, all tables and views are exposed as subcommands. Pass `tables` to restrict to an explicit set:

```python
SqlFlag("mydb.sqlite", tables=["repos", "events"])
```

Unlisted tables are still reachable via `sql` and visible in `schema`. They just don't get auto-generated query subcommands.

### Schema Command

The `schema` command makes the database structure and available operators discoverable.

**List tables:**

```
$ myapp schema
Table           Rows    Columns
repos           142     8
events          1203    5
active_repos    87      8 (view)
```

**Describe a table:**

```
$ myapp schema repos
Table: repos (142 rows)

Column          Type        Operators
name            TEXT        not, contains
language        TEXT        not, contains
stars           INTEGER     not, gt, lt
is_archived     BOOLEAN     not
created_at      DATETIME    not, since, before
description     TEXT        not, contains
homepage_url    TEXT        not, contains
github_id       INTEGER     not, gt, lt

All columns support equality (bare value) and IN (repeated flag).
Reserved (use sql): none
FTS index: no
```

The operator listing is derived from the type mapping:

| Type Category | Available Operators |
|--------------|-------------------|
| TEXT | `not:`, `contains:` |
| INTEGER, REAL | `not:`, `gt:`, `lt:` |
| BOOLEAN | `not:` |
| DATETIME | `not:`, `since:`, `before:` |

All types support bare equality and IN. The schema command documents this per-column so users never need to guess.

The schema command does **not** enforce these type-operator associations. Using `--stars contains:test` is allowed; SQLite handles the type coercion. The schema command describes what is *useful*, not what is *permitted*.

## Output Formatting

- **table**: Rich pretty table. Default when stdout is a TTY.
- **json**: Newline-delimited JSON objects. Default when stdout is piped (structured, preserves types).
- **csv**: CSV with header row.

Auto-detection: if `sys.stdout.isatty()` then `table`, else `json`. `--format` overrides.

## Library API

### Standalone App

```python
from sqlflag import SqlFlag

app = SqlFlag("path/to/db.sqlite")
app.run()
# myapp query repos --language python
# myapp sql "SELECT ..."
# myapp schema repos
```

### Standalone with Table Allowlist

```python
from sqlflag import SqlFlag

app = SqlFlag("path/to/db.sqlite", tables=["repos", "events"])
app.run()
# Only repos and events appear under query
# All tables still reachable via sql and schema
```

### Mount in Existing Typer App

```python
import typer
from sqlflag import SqlFlag

main = typer.Typer()

@main.command()
def my_custom_command():
    ...

# Mount with default query group name
SqlFlag("mydb.sqlite", tables=["repos", "events"]).mount(main)
# myapp query repos --language python
# myapp sql "SELECT ..."

# Or with a custom name for the query group
SqlFlag("mydb.sqlite").mount(main, query_name="db")
# myapp db repos --language python
```

`mount()` adds three commands to the parent app: the query group (configurable name), `sql`, and `schema`. If the parent app already has conflicting command names, the caller resolves the conflict.

### Programmatic Query Engine

```python
from sqlflag import QueryEngine

engine = QueryEngine("mydb.sqlite")
rows = engine.query(
    "repos",
    filters={"language": ["python"], "stars": ["gt:50"]},
    conjunction="all",
    order=["-stars", "name"],
    limit=10,
    columns=["name", "language", "stars"],
)
for row in rows:
    print(row)
```

### Read-Only Enforcement

All database access is read-only. sqlite-utils connection opened with `mode=ro` URI parameter.

## Clash Handling

If a column name matches a reserved flag name:

- The column is **not** exposed as a flag
- It remains accessible via `sql`
- No error, no warning. Silent omission. The `schema` command lists any reserved clashes.

If a column name is not a valid CLI flag (contains spaces, starts with a number, etc.):

- The column is skipped for flag generation
- Accessible via `sql`

Column names with underscores become hyphenated flags: `created_at` becomes `--created-at`. The library maps back to column names internally.

## Type Mapping

Column types from SQLite schema determine which operators the schema command displays:

| SQLite Type | Category | Notes |
|------------|----------|-------|
| TEXT | TEXT | |
| INTEGER | INTEGER | |
| REAL | REAL | Treated same as INTEGER for operator purposes |
| BOOLEAN | BOOLEAN | |
| DATETIME, TIMESTAMP | DATETIME | |
| Other / unrecognized | TEXT | Safe fallback. Includes typeless view columns. |

All flags are `str` at the Typer level (because values may include operator prefixes). Type coercion for SQL parameters is handled by the value parser based on column type.

## Scope Boundaries

**In scope:**

- Auto-generated CLI from SQLite schema
- Table allowlist (`tables` parameter)
- Column flags with operator prefix syntax (7 operators)
- AND/OR conjunction mode (`--all`/`--any`)
- Reserved flags: `--order`, `--limit`, `--columns`, `--format`, `--search`
- Schema inspection with per-column operator documentation
- Raw SQL escape hatch
- Output formatting (table, json, csv) with TTY auto-detection
- Read-only database access
- Library API for standalone, mounting, and programmatic use

**Out of scope:**

- Custom DSL / expression language
- `--where` flag
- Nested boolean logic at the flag level (use `sql`)
- Write operations
- Schema migration or management
- MCP tool generation (future extension)
- Metadata overlays (display columns, default sort, aliases; may revisit)
- Plugin system
- Type enforcement (operators are documented per type but not restricted)
