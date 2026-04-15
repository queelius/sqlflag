# sqlflag

**Auto-generate a CLI from any SQLite database.** Tables become subcommands, columns become filter flags, column types determine the available operators. No configuration. Point it at a `.db` file and the CLI appears.

```bash
$ sqlflag mydb.sqlite repos --language python --stars gt:50 --order -stars --limit 10
```

## Install

```bash
pip install sqlflag
```

## Quick start

```bash
# Inspect the schema
$ sqlflag mydb.sqlite schema
Table                   Rows    Columns
repos                   142     8
events                  1203    5
active_repos (view)     87      8

# See per-column operators for a table
$ sqlflag mydb.sqlite schema repos
Column          Type        Operators
name            TEXT        not, contains
language        TEXT        not, contains
stars           INTEGER     not, gt, lt
created_at      DATETIME    not, since, before
...

# Query with typed operator prefixes
$ sqlflag mydb.sqlite repos --language python --stars gt:50 --format json
$ sqlflag mydb.sqlite events --timestamp since:30d
$ sqlflag mydb.sqlite repos --language python --language go   # IN clause
$ sqlflag mydb.sqlite repos --language python --stars gt:50 --any   # OR across flags

# Raw SQL when flags aren't enough
$ sqlflag mydb.sqlite sql "SELECT r.name, COUNT(e.id) FROM repos r JOIN events e ON e.repo_id = r.id GROUP BY r.id"
```

## Shell completion

The standout feature: completion that knows your schema and (optionally) your data.

### Install completion

```bash
# bash
eval "$(sqlflag --install-completion bash)"

# zsh
eval "$(sqlflag --install-completion zsh)"

# fish
sqlflag --install-completion fish | source
```

Persist by appending to your shell config (e.g. `sqlflag --install-completion bash >> ~/.bashrc`).

### What gets completed

```
$ sqlflag mydb.sqlite re<TAB>
refresh_log  repos

$ sqlflag mydb.sqlite repos --lan<TAB>
--language  --languages

$ sqlflag mydb.sqlite repos --stars <TAB>
gt:  lt:  not:  null

$ sqlflag mydb.sqlite repos --timestamp <TAB>
since:  before:  not:  null

$ sqlflag mydb.sqlite repos --columns name,<TAB>
name,language  name,stars  name,description ...
```

Operator prefixes are **type-aware**: numeric columns offer `gt:` / `lt:`, text columns offer `contains:`, datetime columns offer `since:` / `before:`. The closed set of seven operators is documented per-column via `sqlflag <db> schema <table>`.

### Opt-in: distinct-value completion

For discoverability, sqlflag can tab-complete actual column values. Off by default because it runs SQL on every TAB press:

```bash
export SQLFLAG_COMPLETE_VALUES=1

$ sqlflag mydb.sqlite repos --language P<TAB>
PHP  Python
```

Bounded by cardinality: columns with more than `SQLFLAG_VALUE_COMPLETE_MAX` distinct values (default 100) skip value completion to keep TAB latency predictable.

## Operators

Every column flag accepts `[op:]value`. The seven-operator set is closed; unknown prefixes fall through to literal equality.

| Prefix | SQL | Use case |
|--------|-----|----------|
| *(bare)* | `=` / `IN` | Default. Multiple values produce `IN (...)`. |
| `not:` | `!=` | `not:null` produces `IS NOT NULL`. |
| `gt:` | `>` | Numeric only (but not enforced). |
| `lt:` | `<` | Numeric only (but not enforced). |
| `contains:` | `LIKE '%val%'` | Substring match. Safe: no user wildcards. |
| `since:` | `>=` | Relative (`30d`, `6h`, `2w`, `3mo`, `1y`) or ISO-8601 dates. |
| `before:` | `<` | Same date parsing as `since:`. |

Plus the literal `null` for `IS NULL` queries.

### Composing filters

- Conditions within a single flag always AND together: `--stars gt:5 --stars lt:100` means `stars > 5 AND stars < 100`.
- Conditions across different flags AND together by default: `--language python --stars gt:50`.
- Add `--any` to OR across flags: `--language python --stars gt:50 --any`.

## Output formats

| Format | When | Notes |
|--------|------|-------|
| `table` | Default when stdout is a TTY | Rich-rendered with automatic column widths. |
| `json` | Default when stdout is piped | Newline-delimited JSON. Preserves types. |
| `csv` | Opt-in via `--format csv` | Header row plus data rows. |

Auto-detection can be overridden with `--format`.

## Reserved flags

Every table subcommand also exposes these, in addition to its per-column filter flags:

| Flag | Purpose |
|------|---------|
| `--any` | OR-compose conditions across flags. |
| `--order COL` | `ORDER BY`. Prefix with `-` for DESC: `--order -stars`. Multiple allowed. |
| `--limit N` | `LIMIT`. |
| `--columns A,B,C` | `SELECT` only these columns. |
| `--format F` | Output format (`table`, `json`, `csv`, plus plugin formats). |
| `--search TEXT` | Full-text search (only on tables with an FTS5 index). |

If a column name collides with a reserved flag, the column is silently omitted from flag generation and remains reachable via `sql`.

## Read-only by design

All database access opens SQLite with `mode=ro` URI. Even the `sql` escape hatch cannot write. sqlflag is for exploration, not mutation.

## Programmatic API

`sqlflag` exposes two Python classes for consumers who want filter compilation without the Click layer (e.g. MCP tool handlers, web services, test fixtures):

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

For wide tables, `SqlFlag` accepts a `default_columns` argument that overrides `SELECT *` with a curated display subset. `--columns` at the CLI level still overrides this.

```python
from sqlflag import SqlFlag

app = SqlFlag(
    "mydb.sqlite",
    default_columns={
        "repos": ["name", "language", "stars", "description"],
    },
)
```

## Links

- [Design spec](https://github.com/queelius/sqlflag/blob/main/docs/superpowers/specs/2026-03-17-sqlflag-design.md)
- [Source](https://github.com/queelius/sqlflag)
- [Issues](https://github.com/queelius/sqlflag/issues)

## License

MIT. See [LICENSE](https://github.com/queelius/sqlflag/blob/main/LICENSE).
