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

Add a `RESERVED_COMMANDS = frozenset({"sql", "schema"})` constant in `cli.py` (this is a CLI-layer concern, unlike `RESERVED_FLAGS` which lives in `schema.py` because it is used by `SchemaInfo.flaggable_columns()`).

At build time in `_build()`, if a queryable table/view name is in `RESERVED_COMMANDS`:
- Skip the table command (do not add it to the root group)
- Emit a `warnings.warn()` (consistent with how `RESERVED_FLAGS` collisions are handled in `schema.py`)

Built-in commands always win, even if the user explicitly passes `tables=["sql", "repos"]`. The `schema` command still shows collision-skipped tables in its output (since `_print_schema_overview` iterates raw `table_names()`/`view_names()`, not the filtered command list). Users can query colliding tables via the `sql` command.

## Changes

### `src/sqlflag/cli.py`: `SqlFlag._build()`

Remove the `table_group = click.Group(name="table", ...)` intermediary. Add table commands directly to `root`. Define `RESERVED_COMMANDS` in this module:

```python
import warnings

RESERVED_COMMANDS = frozenset({"sql", "schema"})

# in _build():
def _build(self) -> click.Group:
    root = click.Group()

    for table_name in self._schema.queryable_names():
        if table_name in RESERVED_COMMANDS:
            warnings.warn(
                f"table '{table_name}' skipped "
                f"(conflicts with built-in command). "
                f"Use: sql \"SELECT * FROM {table_name}\"",
            )
            continue
        cmd = self._make_table_command(table_name)
        root.add_command(cmd, name=table_name)

    # sql and schema commands unchanged
    ...
```

### Adapters (`src/sqlflag/adapters/`)

No code changes needed. Adapters iterate `root.commands.items()` and are agnostic to what those commands are. Update docstring examples and inline comments across all three adapters (`click_adapter.py`, `typer_adapter.py`, `argparse_adapter.py`) to remove references to the `table` group.

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
- Schema introspection (`schema.py`)
- Output formatting (`formatter.py`, `formats/`)
- The adapter pattern and `mount()` API
- The `QueryEngine` public API
