# sqlflag Design Spec

**Revised:** 2026-04-14
**Status:** Active
**PyPI name:** `sqlflag`

## Problem

SQLite is the easiest database to carry around, but it has no good ad-hoc CLI. `sqlite3` drops you into a SQL REPL with no flag syntax, no tab completion for columns, no pretty output, no filter composition. Tools like `datasette` are full web apps. The gap is a **CLI that shows up already knowing the schema** so filtering feels like any other Unix command:

```
sqlflag mydb.db repos --language python --stars gt:50 --order -stars --limit 10
```

No configuration. No per-database code. Point it at any SQLite file and the CLI appears.

## What sqlflag is

A **standalone CLI** (`sqlflag`) that reads a SQLite schema, then exposes each table and view as a subcommand with one filter flag per column. Typed operators (`gt:`, `since:`, `contains:`) handle non-equality filtering. Raw SQL is the escape hatch for JOINs, aggregates, and boolean logic too complex for flags.

## What sqlflag is not

- **Not a library for mounting into other CLIs.** Earlier versions shipped Click/Typer/argparse adapters. They were removed because the "zero-code integration" promise breaks down on non-trivial schemas: each host needs `default_columns`, custom column aliases, per-table filters. Host apps are better served by writing a hand-tuned query command against their known schema. sqlflag's value is ad-hoc exploration of *arbitrary* SQLite files.
- **Not a DSL.** No `--where 'stars > 50 AND language = python'`. If flags aren't enough, use `sql`.
- **Not a write tool.** Read-only, always.
- **Not a schema manager.** Doesn't create, alter, or migrate anything.

## Invocation

```
sqlflag <db_path> [COMMAND] [ARGS...]
```

The db path is a required first positional argument. Everything after it is a subcommand plus its own args, handled by Click.

Typical sessions:

```
sqlflag mydb.db                         # list available subcommands (one per table/view + sql + schema)
sqlflag mydb.db schema                  # overview of all tables/views with row counts
sqlflag mydb.db schema repos            # columns, types, and available operators for one table
sqlflag mydb.db repos --help            # per-column flags and reserved flags for this table
sqlflag mydb.db repos --language python
sqlflag mydb.db sql "SELECT name, COUNT(*) FROM events GROUP BY name"
```

`sqlflag` with no args, or `sqlflag --help`, prints a brief usage message. Per-table `--help` comes from Click once a db is loaded.

## Design Principles

- **Uniformity.** One pattern: `--col [op:]value`. No alternative syntax.
- **Two tiers only.** Column flags for single-table AND/OR filtering. Raw SQL for everything else.
- **Derive from structure.** The schema IS the CLI. Adding a column creates a flag. No parallel mappings.
- **Closed operator set.** Seven operators, documented per type. Unknown prefixes are treated as literal values.
- **Trust the user with escape hatches.** Flag-level type restrictions aren't enforced; schema-level operator lists are *documentation*, not gates.

## Architecture

```
sqlflag <db> …
  │
  ▼
__main__.main()          # extracts db_path from argv
  │
  ▼
SqlFlag (cli.py)         # builds the Click group from schema
  │
  ├── SchemaInfo         # table/view/column introspection
  ├── QueryEngine        # filter compilation → parameterized SQL
  │     └── parser.py    # op:value parsing and type coercion
  └── formatter.py       # table / json / csv output with TTY autodetect
```

### Dependencies

- **sqlite-utils**: schema introspection, FTS support, read-only connection handling.
- **click**: CLI framework. Chosen over Typer because column flags are determined at runtime from the schema, and Click's `click.Command(params=[...])` supports dynamic params naturally.
- **rich**: pretty-table output.

No custom SQL parser. SQLite itself validates queries and reports errors.

## Two Tiers

### Tier 1: Column flags

Each table/view becomes a root subcommand. Every subcommand gets:

- One `--colname` flag per column (all `multiple=True`, all `str` at the Click level)
- Reserved flags for ordering, output, and conjunction (see [Reserved Flags](#reserved-flags))
- A `--search` flag iff the table has an FTS index

```
sqlflag mydb.db repos --language python --stars gt:50 --order -stars --limit 10
sqlflag mydb.db events --timestamp since:30d --format json
sqlflag mydb.db repos --language python --language go          # IN clause
sqlflag mydb.db repos --language python --stars gt:50 --any    # OR across flags
```

Default is AND across flags; `--any` switches to OR. Conditions *within* a single flag always AND together (e.g., `--stars gt:5 --stars lt:100` is always `stars > 5 AND stars < 100`).

### Tier 2: Raw SQL

```
sqlflag mydb.db sql "SELECT r.name, COUNT(e.id) FROM repos r JOIN events e ON e.repo_id = r.id GROUP BY r.id"
```

Read-only enforcement via `mode=ro` URI parameter on the sqlite connection. Full SQL power for anything flags can't do.

## Value Syntax

Each flag value is parsed as `[op:]value`. Rules are applied in this order:

1. If the value starts with `KNOWN_OP:` where `KNOWN_OP` is in the closed operator set, apply that operator to the rest
2. If the value is literally `null`, produce `IS NULL`
3. Otherwise, treat as a literal for equality

Rule 1 means `foo:bar` (with `foo` not a known operator) is treated as the literal string `"foo:bar"` for equality. The colon is only special when preceded by a known operator name.

The literal string `"null"` cannot be queried via flags; use `sql`.

### Combining values on one flag

- Bare values collect into `= val` (single) or `IN (val1, val2, …)` (multiple)
- Each operator-prefixed value becomes its own condition
- All conditions within a flag AND together, regardless of `--any` mode
- Conditions across different flags are joined by the conjunction mode (AND default, OR with `--any`)

### Operator Table

| Prefix | SQL | Notes |
|--------|-----|-------|
| *(bare)* | `=` / `IN` | Default. Multiple bare values → `IN`. |
| `not:` | `!=` | `not:null` produces `IS NOT NULL`. |
| `gt:` | `>` | |
| `lt:` | `<` | |
| `contains:` | `LIKE '%val%'` | Substring match; no user-supplied wildcards. |
| `since:` | `>=` | Relative or absolute dates. |
| `before:` | `<` | Same date parsing as `since:`. |

Seven operators. Closed set. Unknown prefixes fall through to literal equality.

### Relative Date Format

| Unit | Meaning | Example |
|------|---------|---------|
| `min` | minutes | `30min` |
| `h` | hours | `6h` |
| `d` | days | `30d` |
| `w` | weeks | `4w` |
| `mo` | months | `3mo` |
| `y` | years | `1y` |

Absolute ISO-8601 dates pass through as-is. Relative dates are resolved to an ISO-8601 string at query time. Works correctly for date/datetime columns stored in ISO-8601 format (SQLite convention).

## Reserved Flags

Every table subcommand includes these. Columns with the same name are silently omitted from flag generation and remain reachable via `sql`.

| Flag | Purpose | Notes |
|------|---------|-------|
| `--any` | OR-compose conditions across flags | Default is AND (no flag needed). |
| `--order COL` | `ORDER BY` | `multiple=True`. Prefix with `-` for DESC. |
| `--limit N` | `LIMIT` | |
| `--columns A,B,C` | `SELECT` only these columns | Overrides `default_columns`. |
| `--format F` | Output format: `table`, `json`, `csv` | Auto-detects: `table` for TTY, `json` for pipe. |
| `--search TEXT` | Full-text search | Only present on tables with FTS. ANDed with column filters. |

**Reserved names:** `any`, `order`, `limit`, `columns`, `format`, `search`, `help`. Columns with these names fall through to `sql`-only access.

## Reserved Commands

Two built-in commands take precedence over table subcommands:

- `sql`: raw SQL
- `schema`: structure inspection

If a table or view is named `sql` or `schema`, it is **skipped at CLI build time** with a `warnings.warn()` message. It remains visible in `schema` output and reachable via `sql "SELECT * FROM <name>"`. Built-in commands always win, even if the caller passes `tables=["sql", ...]` explicitly.

## Command Structure

```
sqlflag <db>
├── <table>          (one per queryable table and view, except reserved names)
├── <view>           (views are treated identically to tables)
├── sql              (raw SQL)
└── schema           (structure inspection)
```

### Views

Views appear as subcommands alongside tables with no UX distinction. The `schema` overview marks them with a `(view)` suffix for discoverability.

### Table allowlist

By default, all tables and views are exposed. Pass `tables` to the `SqlFlag` constructor to restrict:

```python
SqlFlag("mydb.sqlite", tables=["repos", "events"])
```

Unlisted tables remain reachable via `sql` and visible in `schema`. They simply don't get auto-generated subcommands.

## Default Columns

Wide tables produce unusable default output. A table with 50+ columns rendered as a Rich table in a terminal is visual noise, and `SELECT *` over wide rows in JSON is unwieldy to read. `default_columns` solves this:

```python
SqlFlag(
    "mydb.sqlite",
    default_columns={
        "repos": ["name", "language", "stars", "description"],
    },
)
```

Semantics:

- If the user passes `--columns A,B,C`, those win.
- Otherwise, if the table has a `default_columns` entry, those are used.
- Otherwise, all columns are returned (`SELECT *`).

The standalone `sqlflag` CLI does not currently accept `default_columns` on the command line; it is a Python-API feature for consumers that embed `SqlFlag` or wrap it for a specific database. A future enhancement could read it from a sidecar config file (e.g., `mydb.db.sqlflag.toml`), but that is out of scope for v1.

**Rationale:** We discovered this problem when attempting to auto-generate a CLI over repoindex's `repos` table (55 columns). Without per-table default columns, the output was unreadable regardless of format. The feature is first-class because the problem is inherent to real-world schemas, not a corner case.

## Schema Command

Makes the database structure and available operators discoverable.

**Overview:**

```
$ sqlflag mydb.db schema
Table                   Rows    Columns
repos                   142     8
events                  1203    5
active_repos (view)     87      8
```

**Table detail:**

```
$ sqlflag mydb.db schema repos
Table: repos (142 rows)

Column          Type        Operators
name            TEXT        not, contains
language        TEXT        not, contains
stars           INTEGER     not, gt, lt
is_archived     BOOLEAN     not
created_at      DATETIME    not, since, before
description     TEXT        not, contains

All columns support equality (bare value) and IN (repeated flag).
Reserved (use sql): none
FTS index: no
```

### Type → operator mapping (documentation only, not enforcement)

| Type category | Operators shown |
|---------------|-----------------|
| TEXT | `not:`, `contains:` |
| INTEGER, REAL | `not:`, `gt:`, `lt:` |
| BOOLEAN | `not:` |
| DATETIME, TIMESTAMP | `not:`, `since:`, `before:` |
| Other / unrecognized | TEXT (safe fallback, includes typeless view columns) |

All types additionally support bare equality and IN via repeated flags. Using an operator outside its documented set is allowed (e.g., `--stars contains:test`); SQLite handles the coercion. The schema command describes what is *useful*, not what is *permitted*.

## Output Formatting

- **table**: Rich pretty table. Default when `stdout.isatty()`.
- **json**: Newline-delimited JSON objects. Default when stdout is piped. Preserves types.
- **csv**: CSV with header row.

`--format` overrides auto-detection.

## Shell Completion

sqlflag ships with shell completion derived from the database schema and (optionally) its data. Supports bash, zsh, and fish.

### Installation

The simplest path uses the built-in helper:

```bash
# Print and eval in one step
eval "$(sqlflag --install-completion bash)"

# Or persist by appending to your shell config
sqlflag --install-completion bash >> ~/.bashrc
sqlflag --install-completion zsh  >> ~/.zshrc
sqlflag --install-completion fish >> ~/.config/fish/completions/sqlflag.fish
```

The completion script is the same one Click emits via the standard `_SQLFLAG_COMPLETE=<shell>_source sqlflag` convention; the `--install-completion` flag exists for discoverability.

### What gets completed

| Scope | Completed tokens | Source |
|-------|------------------|--------|
| Positional 1 (db path) | file paths | Click default for `click.Path` |
| Subcommand | table/view names, `sql`, `schema` | `SchemaInfo.queryable_names()` |
| Flag name | `--language`, `--stars`, etc. | `SchemaInfo.flaggable_columns()` |
| `--format` | `table`, `json`, `csv` (and any plugin format) | `click.Choice` |
| `--columns` | column names, comma-aware | `ColumnListType` |
| `--order` | column names (asc only via TAB) | `OrderType` |
| Filter value (Tier 2) | operator prefixes by column type | `FilterValueType` |
| Filter value (Tier 2) | the literal `null` | `FilterValueType` |
| Filter value (Tier 3, opt-in) | distinct column values | `FilterValueType` + `QueryEngine.distinct_values_bounded` |

### Tier 3: opt-in value completion

Distinct-value completion is **off by default** because it issues SQL on every TAB press. Enable it explicitly:

```bash
export SQLFLAG_COMPLETE_VALUES=1
```

Bounded by cardinality. Columns with more than `SQLFLAG_VALUE_COMPLETE_MAX` distinct values (default 100) skip value completion to keep latency predictable. The check uses a single `SELECT DISTINCT col FROM tab WHERE col IS NOT NULL LIMIT N+1` query: if N+1 rows come back, cardinality exceeds the ceiling and only operators are returned.

```bash
# Lower the ceiling for very ad-hoc DBs
export SQLFLAG_VALUE_COMPLETE_MAX=20
```

When the user has already typed an operator prefix (e.g., `gt:`), value completion is suppressed for that token; Tier 3 only fires for bare incompletes.

### Known limitation: `--order -COL` for descending

The `-` prefix on `--order` produces DESC at runtime, but tab-completing it does not work. Both bash and Click treat a token starting with `-` at a value position as the start of a new option flag, so our `OrderType.shell_complete` is not reached. Workaround: type the `-COL` value yourself, or use `--order=-COL` with the `=` form. Tab-completion still works for ascending order (`--order col<TAB>`).

### Error handling guarantee

Shell completion **never raises**. All data access in Tier 3 is wrapped in a broad `try/except` so a broken database connection, missing table, or query error degrades silently to "no candidates returned" rather than crashing the user's shell. This is the one place in the codebase where suppressing exceptions is the correct policy: a broken completion is strictly better than a crashed shell.

## Library API

### Standalone embedding

```python
from sqlflag import SqlFlag

app = SqlFlag("path/to/db.sqlite")
app.click_app(["repos", "--language", "python"])
```

### With table allowlist and default columns

```python
SqlFlag(
    "mydb.sqlite",
    tables=["repos", "events"],
    default_columns={"repos": ["name", "language", "stars"]},
)
```

### Programmatic query engine

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
```

`QueryEngine` is a clean public API for callers that want filter compilation without the Click layer (e.g., MCP tool handlers, web services, test fixtures).

## Clash Handling

| Clash | Outcome |
|-------|---------|
| Column name matches reserved flag (`any`, `order`, `limit`, `columns`, `format`, `search`, `help`) | Column omitted from flags; reachable via `sql`; noted in `schema` output. |
| Column name has invalid CLI characters (spaces, leading digits, etc.) | Column skipped for flag generation; reachable via `sql`. |
| Table name matches reserved command (`sql`, `schema`) | Subcommand skipped with `warnings.warn()`; table visible in `schema`; reachable via `sql "SELECT * FROM <name>"`. |
| Column name is SQLite reserved word | Bracket-quoted (`[col]`) throughout generated SQL. |

Column names with underscores become hyphenated flags: `created_at` → `--created-at`. The library maps back to column names internally.

## Read-Only Enforcement

All database access opens the connection with `file:<path>?mode=ro` via URI. Even the `sql` escape hatch cannot write. This is a library-level invariant, not a user-facing option.

## Scope

**In scope**
- Auto-generated CLI from SQLite schema (tables + views)
- Column flags with a closed 7-operator prefix syntax
- AND/OR conjunction across flags
- Reserved flags: `--any`, `--order`, `--limit`, `--columns`, `--format`, `--search`
- Reserved command collision handling (`sql`, `schema`)
- `default_columns` for wide-schema UX
- Schema inspection with per-column operator documentation
- Raw SQL escape hatch (read-only)
- Output formats: table / json / csv with TTY auto-detect
- Standalone `sqlflag` command via `[project.scripts]` entry point
- `SqlFlag` and `QueryEngine` public Python APIs

**Out of scope**
- Mounting into host CLI frameworks (removed; see [What sqlflag is not](#what-sqlflag-is-not))
- `--where` DSL or nested boolean flag expressions
- Write operations of any kind
- Schema migration or management
- Per-database config files for `default_columns` (possible future enhancement)
- MCP tool generation (possible future extension)
- Type enforcement (operators are documented per type, not restricted)
