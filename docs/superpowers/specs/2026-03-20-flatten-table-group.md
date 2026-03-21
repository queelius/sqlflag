# Flatten the `table` Command Group

**Date:** 2026-03-20
**Status:** Approved
**Scope:** CLI structure change: removes the `table` subgroup, promotes table commands to root level

## Problem

The current CLI nests table commands inside a `table` subgroup:

```
root
├── table
│   ├── repos
│   └── events
├── sql
└── schema
```

This creates unnecessary depth. Standalone usage is `table repos --stars gt:5`; mounted usage is `query table repos --stars gt:5` (three levels deep before reaching a filter flag). The `table` group was defensive namespacing against collisions with `sql` and `schema`, but the cost in UX outweighs the benefit.

## Solution

Promote table/view commands to direct children of the root group:

```
root
├── repos
├── events
├── sql
└── schema
```

### CLI paths after change

| Context | Before | After |
|---------|--------|-------|
| Standalone | `table repos --stars gt:5` | `repos --stars gt:5` |
| Mounted (`query_name="db"`) | `db table repos --stars gt:5` | `db repos --stars gt:5` |
| SQL | `sql "SELECT ..."` | `sql "SELECT ..."` (unchanged) |
| Schema | `schema repos` | `schema repos` (unchanged) |

### Collision handling

Add a `RESERVED_COMMANDS = frozenset({"sql", "schema"})` constant alongside the existing `RESERVED_FLAGS`.

At build time in `_build()`, if a queryable table/view name is in `RESERVED_COMMANDS`:
- Skip the table command (do not add it to the root group)
- Emit a warning via `click.echo(f"Warning: table '{name}' skipped (conflicts with built-in command). Use: sql \"SELECT * FROM {name}\"", err=True)`

The built-in `sql` and `schema` commands always win. Users can still query colliding tables via the `sql` command.

## Changes

### `src/sqlflag/cli.py`: `SqlFlag._build()`

Remove the `table_group = click.Group(name="table", ...)` intermediary. Add table commands directly to `root`:

```python
def _build(self) -> click.Group:
    root = click.Group()

    for table_name in self._schema.queryable_names():
        if table_name in RESERVED_COMMANDS:
            click.echo(
                f"Warning: table '{table_name}' skipped "
                f"(conflicts with built-in command). "
                f"Use: sql \"SELECT * FROM {table_name}\"",
                err=True,
            )
            continue
        cmd = self._make_table_command(table_name)
        root.add_command(cmd, name=table_name)

    # sql and schema commands unchanged
    ...
```

### `src/sqlflag/schema.py`

Add `RESERVED_COMMANDS` constant:

```python
RESERVED_COMMANDS = frozenset({"sql", "schema"})
```

### Adapters (`src/sqlflag/adapters/`)

No changes needed. Adapters iterate `root.commands.items()` and are agnostic to what those commands are.

### Tests (`tests/test_cli.py`)

- Remove `"table"` from all CLI invocation args (e.g., `["table", "repos", ...]` becomes `["repos", ...]`)
- Remove `"table"` from adapter test paths (e.g., `["query", "table", "repos", ...]` becomes `["query", "repos", ...]`)
- Add collision tests:
  - Create a db with a table named `sql`, verify it is skipped
  - Verify the `sql` command still works when a table named `sql` exists
  - Verify warning is emitted to stderr on collision

### `CLAUDE.md`

Update the "Command structure" paragraph to reflect the flattened hierarchy.

## What does NOT change

- Value parsing (`parser.py`)
- Query compilation (`query.py`)
- Schema introspection (`schema.py`, except the new constant)
- Output formatting (`formatter.py`, `formats/`)
- The adapter pattern and `mount()` API
- The `QueryEngine` public API
