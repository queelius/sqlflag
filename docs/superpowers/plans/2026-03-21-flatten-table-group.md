# Flatten Table Group Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the `table` subgroup from the CLI, promoting table commands to root-level siblings of `sql` and `schema`.

**Architecture:** The `_build()` method in `cli.py` currently creates a `table` Click Group and nests per-table commands inside it. We remove the intermediary group and add table commands directly to root, with collision detection for reserved command names (`sql`, `schema`).

**Tech Stack:** Python, Click, pytest

**Spec:** `docs/superpowers/specs/2026-03-20-flatten-table-group.md`

---

### Task 1: Flatten `_build()` and add collision handling

**Files:**
- Modify: `src/sqlflag/cli.py:1-8` (imports), `src/sqlflag/cli.py:27-35` (`_build` method)

- [ ] **Step 1: Write the failing test for flattened CLI structure**

Add to `tests/test_cli.py`:

```python
class TestFlattenedStructure:
    def test_table_commands_at_root(self, sample_db):
        """Tables are direct children of root, not nested under 'table' group."""
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, ["repos", "--format", "json"])
        assert result.exit_code == 0, result.output
        lines = result.output.strip().split("\n")
        assert len(lines) == 4

    def test_table_subgroup_removed(self, sample_db):
        """The 'table' subcommand should no longer exist."""
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, ["table", "repos", "--format", "json"])
        assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::TestFlattenedStructure -v`
Expected: FAIL (repos is still nested under `table`, and `table` group still exists)

- [ ] **Step 3: Implement the flattened `_build()`**

In `src/sqlflag/cli.py`, add `import warnings` and `RESERVED_COMMANDS` at module level, then replace the `_build` method's table group logic:

```python
# Add to imports (line 1-7):
import warnings

# Add after imports:
RESERVED_COMMANDS = frozenset({"sql", "schema"})

# Replace _build method (lines 27-66):
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

    # sql command (unchanged from here)
    engine = self._engine
    ...
```

The sql command, schema command, and everything below `_build` remains unchanged.

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `pytest tests/test_cli.py::TestFlattenedStructure -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sqlflag/cli.py tests/test_cli.py
git commit -m "feat: flatten table commands to root level

Remove the 'table' subgroup. Table/view commands are now direct
children of the root Click group alongside sql and schema.
Tables named 'sql' or 'schema' are skipped with a warning."
```

---

### Task 2: Add collision tests

**Files:**
- Modify: `tests/conftest.py` (new fixture)
- Modify: `tests/test_cli.py` (new test class)

- [ ] **Step 1: Add a fixture for a database with a colliding table name**

Add to `tests/conftest.py`:

```python
@pytest.fixture
def collision_db(tmp_path):
    """Database with a table named 'sql' to test collision handling."""
    db_path = str(tmp_path / "collision.db")
    db = Database(db_path)
    db.execute("CREATE TABLE sql (id INTEGER, value TEXT)")
    db["sql"].insert_all([{"id": 1, "value": "one"}])
    db.execute("CREATE TABLE repos (name TEXT, stars INTEGER)")
    db["repos"].insert_all([{"name": "alpha", "stars": 100}])
    return db_path
```

- [ ] **Step 2: Write collision tests**

Add to `tests/test_cli.py`:

```python
class TestCommandCollision:
    def test_colliding_table_skipped(self, collision_db):
        """A table named 'sql' should not become a subcommand."""
        with pytest.warns(UserWarning, match="table 'sql' skipped"):
            app = SqlFlag(collision_db)
        runner = CliRunner()
        # 'sql' should be the built-in command, not the table
        result = runner.invoke(app.click_app, [
            "sql", "SELECT count(*) as n FROM sql", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert rows[0]["n"] == 1

    def test_non_colliding_tables_still_work(self, collision_db):
        """Other tables should still be queryable as subcommands."""
        with pytest.warns(UserWarning, match="table 'sql' skipped"):
            app = SqlFlag(collision_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, ["repos", "--format", "json"])
        assert result.exit_code == 0, result.output

    def test_schema_shows_colliding_table(self, collision_db):
        """Schema command should still list skipped tables."""
        with pytest.warns(UserWarning, match="table 'sql' skipped"):
            app = SqlFlag(collision_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, ["schema"])
        assert result.exit_code == 0
        assert "sql" in result.output
```

Add `import pytest` to the top of `tests/test_cli.py` (it is not currently imported).

- [ ] **Step 3: Run collision tests**

Run: `pytest tests/test_cli.py::TestCommandCollision -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_cli.py
git commit -m "test: add collision handling tests for reserved command names"
```

---

### Task 3: Update existing tests to remove `"table"` segment

**Files:**
- Modify: `tests/test_cli.py` (all existing test classes)

Every test that invokes the CLI with `["table", ...]` needs that segment removed. Every test that uses `["query", "table", ...]` or `["browse", "table", ...]` or `["db", "table", ...]` also needs the `"table"` segment removed.

- [ ] **Step 1: Update all direct CLI invocations**

Across all test classes, apply these search-and-replace patterns:

| Find | Replace |
|------|---------|
| `["table", "repos",` | `["repos",` |
| `["table", "active_repos",` | `["active_repos",` |
| `["table", "events",` | `["events",` |

This affects `TestQueryCommands`, `TestTableAllowlist`, and `TestSearchCommand`.

- [ ] **Step 2: Update all mounted CLI invocations**

| Find | Replace |
|------|---------|
| `["query", "table", "repos",` | `["query", "repos",` |
| `["browse", "table", "repos",` | `["browse", "repos",` |
| `["db", "table", "repos",` | `["db", "repos",` |

This affects `TestClickAdapter`, `TestTyperAdapter`, `TestArgparseAdapter`, and `TestConvenienceMount`.

- [ ] **Step 3: Update stale comments**

In `TestClickAdapter`: change `# Table commands under "query table" path` to `# Table commands under "query" path`
In `TestArgparseAdapter`: change `# Table commands go under: myapp query table repos ...` to `# Table commands go under: myapp query repos ...`

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Run coverage**

Run: `pytest tests/ --cov=sqlflag --cov-report=term-missing`
Expected: No regressions in coverage

- [ ] **Step 6: Commit**

```bash
git add tests/test_cli.py
git commit -m "test: update all CLI tests for flattened command structure"
```

---

### Task 4: Update adapter docstrings and comments

**Files:**
- Modify: `src/sqlflag/adapters/click_adapter.py` (docstring)
- Modify: `src/sqlflag/adapters/argparse_adapter.py` (inline comment)

- [ ] **Step 1: Update click adapter docstring**

In `src/sqlflag/adapters/click_adapter.py`, update the `mount` function docstring. Remove `table` from the example CLI paths:

```python
def mount(app: click.Group, sqlflag: SqlFlag, query_name: str = "query") -> click.Group:
    """Mount all sqlflag commands as a single group in a Click app.

    Creates a command group (default name "query") containing table
    subcommands, sql, and schema, all namespaced to avoid conflicts.

    Usage:
        from sqlflag.adapters.click_adapter import mount
        mount(my_click_group, SqlFlag("db.sqlite"), query_name="browse")
        # my_click_group browse repos --language Python
        # my_click_group browse schema repos
        # my_click_group browse sql "SELECT ..."
    """
    return ClickAdapter().mount(app, sqlflag, query_name)
```

- [ ] **Step 2: Update argparse adapter inline comment**

In `src/sqlflag/adapters/argparse_adapter.py`, change the comment in `ArgparseAdapter.mount()`:
- Find: `# Transfer all root commands (table group, sql, schema)`
- Replace: `# Transfer all root commands (table subcommands, sql, schema)`

Note: The typer adapter docstring has no CLI example paths, so no changes needed there. The argparse adapter docstring examples already show flat paths.

- [ ] **Step 3: Run tests to verify nothing broke**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/sqlflag/adapters/
git commit -m "docs: update adapter docstrings for flattened command structure"
```

---

### Task 5: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md:30` (Command structure paragraph)

- [ ] **Step 1: Update the Command structure paragraph**

Replace the current text at line 30:

```
**Command structure:** Tables are namespaced under a `table` subgroup to avoid collisions with built-in commands (`sql`, `schema`). When mounted via an adapter (e.g., `query_name="db"`), the path is `db table repos --stars gt:5`. Direct `click_app` usage: `table repos --stars gt:5`.
```

With:

```
**Command structure:** Tables are promoted to top-level commands alongside `sql` and `schema`. If a table name collides with a built-in command, it is skipped with a warning (use the `sql` command to query it directly). When mounted via an adapter (e.g., `query_name="db"`), the path is `db repos --stars gt:5`. Direct `click_app` usage: `repos --stars gt:5`.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for flattened command structure"
```
