# Remove Adapter ABC and Class Wrappers

**Date:** 2026-03-21
**Status:** Approved
**Scope:** Simplify adapter layer by removing the ABC and class wrappers, keeping only module-level functions

## Problem

Each adapter has both a class (`ClickAdapter`, `TyperAdapter`, `ArgparseAdapter`) inheriting from an `Adapter` ABC, and a module-level `mount()` function that instantiates the class and calls its one method. The ABC provides no runtime value: no isinstance checks, no polymorphism, no shared behavior. The classes are pure ceremony.

## Solution

Delete the `Adapter` ABC. Collapse each adapter class into its module-level `mount()` function. The function signatures and behavior remain identical.

## Changes

### `src/sqlflag/adapters/__init__.py`

Remove the `Adapter` ABC. Keep only the module docstring.

### `src/sqlflag/adapters/click_adapter.py`

Delete `ClickAdapter` class. Inline its logic into the `mount()` function:

```python
def mount(app: click.Group, sqlflag: SqlFlag, query_name: str = "query") -> click.Group:
    root = sqlflag.click_app
    group = click.Group(name=query_name, help="Query database tables.")
    for name, cmd in root.commands.items():
        group.add_command(cmd, name=name)
    app.add_command(group)
    return app
```

### `src/sqlflag/adapters/typer_adapter.py`

Delete `TyperAdapter` class. Inline its logic into the `mount()` function:

```python
def mount(app: typer.Typer, sqlflag: SqlFlag, query_name: str = "query") -> click.Group:
    click_group = typer.main.get_group(app)
    root = sqlflag.click_app
    group = click.Group(name=query_name, help="Query database tables.")
    for name, cmd in root.commands.items():
        group.add_command(cmd, name=name)
    click_group.add_command(group)
    return click_group
```

### `src/sqlflag/adapters/argparse_adapter.py`

Delete `ArgparseAdapter` class. Move `_find_or_create_subparsers` to module level as a private function. Inline the mount logic into the `mount()` function. `invoke()` is unchanged.

### Tests

No test changes needed. All tests call the module-level `mount()` functions or `SqlFlag.mount()`, never the adapter classes directly.

## What does NOT change

- `SqlFlag.mount()` auto-detection logic
- All `mount()` function signatures
- `invoke()` in argparse adapter
- Any test code
