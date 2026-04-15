# Shell Completion Implementation Plan

**Date:** 2026-04-14
**Status:** Draft
**Spec section to add:** "Shell Completion" in `docs/superpowers/specs/2026-03-17-sqlflag-design.md`

## Goal

Ship three tiers of shell completion for sqlflag:

1. **Tier 1 (schema-free):** subcommand names, flag names, `--format` choices, `--columns` column names, `--order` column names with optional `-` prefix.
2. **Tier 2 (schema-aware):** per-column operator prefixes (`gt:`, `since:`, etc.) based on column type.
3. **Tier 3 (data-aware, opt-in):** distinct column values from the database, gated by cardinality and an env-var toggle.

Support bash, zsh, fish (whatever Click supports out of the box). Provide a one-line install command or documented eval snippet.

## Architecture summary

The critical change is the entry point. Click's shell-completion machinery (`click.shell_completion`) walks the command tree from the top-level group based on `COMP_WORDS`. It assumes all arguments (including positional ones) are Click parameters. Today's `__main__.py` strips the db path from `sys.argv` before Click sees it, which breaks completion.

Solution: convert the entry point into a **lazy Click group** where:
- `db_path` is a proper `@click.argument`
- `list_commands(ctx)` and `get_command(ctx, name)` build `SqlFlag(db_path)` on demand using `ctx.params["db_path"]`, caching the instance on `ctx.meta`

This is the standard Click pattern for dynamic CLIs (see [Click: "Complex Applications"](https://click.palletsprojects.com/en/stable/complex/)). It gives us shell completion **for free** for subcommand names and `--format` choices. The remaining tiers are implemented as custom `ParamType.shell_complete` hooks.

## Non-goals

- Custom bash script distribution. We rely on Click's built-in `_SQLFLAG_COMPLETE` mechanism.
- Fuzzy matching during completion. Only prefix matching (Click default).
- Remembering user history. Each completion invocation is a fresh process.
- Persistent value caching in Phase 3. Start with a per-invocation LIMIT; revisit caching only if users complain about latency.

## Phases and task order

Phases depend linearly. Within a phase, tasks can sometimes be parallelized (noted).

### Phase 0: Entry-point refactor to lazy Click group

Prerequisite for all completion work. Independently valuable (cleaner architecture, proper `--help`).

### Phase 1: Tier 1 completion

Subcommand completion comes free from Phase 0. Explicit work needed for `--columns` and `--order` column-name completion.

### Phase 2: Tier 2 completion

Custom `ParamType` for each column's filter flag, offering operator prefixes based on column type.

### Phase 3: Tier 3 completion

Extend the Phase 2 `ParamType` to also offer distinct values, with cardinality gating and an env-var gate.

### Phase 4: Install UX and docs

A subcommand or CLI flag that emits shell-completion snippets. Spec update. CLAUDE.md update.

---

## Phase 0: Entry-point refactor

### Task 0.1: Create `SqlFlagGroup` lazy Click group

**Files:**
- Modify: `src/sqlflag/__main__.py` (full rewrite)
- Add: `src/sqlflag/lazy_group.py` (new, ~40 lines) *or* inline in `__main__.py`. Prefer inline until the file grows past ~80 lines; keeps the public surface minimal.

**Implementation:**

```python
# src/sqlflag/__main__.py
"""Standalone CLI: `sqlflag <db_path> [subcommand] [args...]`."""

import click

from sqlflag.cli import SqlFlag


class SqlFlagGroup(click.Group):
    """A Click group whose subcommands are derived from a SQLite database at runtime."""

    def _sqlflag(self, ctx):
        sf = ctx.meta.get("sqlflag.instance")
        if sf is not None:
            return sf
        db_path = ctx.params.get("db_path")
        if not db_path:
            return None
        sf = SqlFlag(db_path)
        ctx.meta["sqlflag.instance"] = sf
        return sf

    def list_commands(self, ctx):
        sf = self._sqlflag(ctx)
        if sf is None:
            return []
        return sorted(sf.click_app.commands)

    def get_command(self, ctx, name):
        sf = self._sqlflag(ctx)
        if sf is None:
            return None
        return sf.click_app.commands.get(name)


@click.group(
    cls=SqlFlagGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
@click.argument(
    "db_path",
    type=click.Path(exists=True, dir_okay=False),
    required=False,
)
@click.pass_context
def main(ctx, db_path):
    """sqlflag: auto-generate CLIs from SQLite databases.

    Usage: sqlflag <db_path> [COMMAND] [ARGS...]

    Tables and views become subcommands. Columns become filter flags.
    Use `sqlflag <db_path> schema` to inspect structure.
    Use `sqlflag <db_path> sql "..."` for raw SQL.
    """
    if db_path is None and ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)
    if db_path is not None and ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)


if __name__ == "__main__":
    main()
```

**Why `invoke_without_command=True`:** lets us handle `sqlflag` (no args) and `sqlflag <db>` (no subcommand) as help-printing no-ops rather than errors. Cleaner UX than current custom `USAGE` string.

**Why cache on `ctx.meta`, not on the group instance:** the group is a module-level singleton; `ctx.meta` gives per-invocation scope, avoiding stale state if anyone calls `main()` twice in-process (e.g., tests).

**Why `required=False` for db_path:** enables `sqlflag --help` without a db. Click then complains if a subcommand is given without db_path, which is correct behavior.

### Task 0.2: Update tests for new entry point

**Files:**
- Modify: `tests/test_cli.py` (new `TestEntryPoint` class, ~8 tests)
- Existing `TestQueryCommands`, etc. use `SqlFlag(...).click_app` directly and are unaffected.

**Tests:**

```python
class TestEntryPoint:
    def test_no_args_shows_help(self):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        assert "sqlflag" in result.output.lower()
        assert "Usage:" in result.output

    def test_help_without_db(self):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0

    def test_db_path_lists_subcommands(self, sample_db):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, [sample_db, "--help"])
        assert result.exit_code == 0
        assert "repos" in result.output
        assert "sql" in result.output
        assert "schema" in result.output

    def test_db_then_table_runs_query(self, sample_db):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, [sample_db, "repos", "--format", "json"])
        assert result.exit_code == 0

    def test_db_then_sql(self, sample_db):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, [sample_db, "sql", "SELECT count(*) n FROM repos", "--format", "json"])
        assert result.exit_code == 0

    def test_db_then_schema(self, sample_db):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, [sample_db, "schema"])
        assert result.exit_code == 0

    def test_nonexistent_db_errors(self):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, ["/no/such/file.db", "repos"])
        assert result.exit_code != 0

    def test_table_help(self, sample_db):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, [sample_db, "repos", "--help"])
        assert result.exit_code == 0
        assert "--language" in result.output
        assert "--stars" in result.output
```

### Task 0.3: Verify downstream usage still works

**Files:**
- Run: full test suite
- Manual: `sqlflag ~/.repoindex/index.db schema` and `sqlflag ~/.repoindex/index.db repos --language Python --limit 3 --format json`

**Acceptance:** all existing 97 tests pass + 8 new tests in `TestEntryPoint`.

---

## Phase 1: Tier 1 (schema-free) completion

After Phase 0, Click provides subcommand completion, flag-name completion, and `--format` choice completion automatically. What remains: custom completion for `--columns` (comma-separated list of column names) and `--order` (single column name, optionally prefixed with `-`).

### Task 1.1: `ColumnListType` for `--columns`

**Files:**
- Modify: `src/sqlflag/cli.py` (add `ColumnListType` at module scope, wire into `_make_table_command`)

**Implementation:**

```python
# src/sqlflag/cli.py (new at module scope, near RESERVED_COMMANDS)
from click.shell_completion import CompletionItem


class ColumnListType(click.ParamType):
    """Comma-separated list of column names. Completes against remaining columns."""

    name = "column_list"

    def __init__(self, columns: list[str]):
        self._columns = columns

    def convert(self, value, param, ctx):
        return value  # no conversion

    def shell_complete(self, ctx, param, incomplete):
        # Split on comma, complete the last token
        parts = incomplete.split(",")
        already = {p.strip() for p in parts[:-1]}
        prefix_so_far = ",".join(parts[:-1])
        if prefix_so_far:
            prefix_so_far += ","
        current = parts[-1]
        items = []
        for col in self._columns:
            if col in already:
                continue
            if col.startswith(current):
                items.append(CompletionItem(prefix_so_far + col))
        return items
```

**Wire-up in `_make_table_command`:**

```python
all_column_names = [c.name for c in schema.columns(table_name)]
# ...
click.Option(
    ["--columns"], default=None,
    type=ColumnListType(all_column_names),
    help="Comma-separated columns to display.",
),
```

**Tests (new `TestCompletionTier1` class in `tests/test_cli.py`):**

```python
def test_columns_completion_first_token(self, sample_db):
    from sqlflag.cli import SqlFlag
    app = SqlFlag(sample_db)
    repos_cmd = app.click_app.commands["repos"]
    param = next(p for p in repos_cmd.params if p.name == "columns")
    ctx = click.Context(repos_cmd)
    items = [c.value for c in param.type.shell_complete(ctx, param, "")]
    assert "name" in items
    assert "language" in items

def test_columns_completion_after_comma(self, sample_db):
    ...
    items = [c.value for c in param.type.shell_complete(ctx, param, "name,")]
    assert "name,language" in items
    assert "name,name" not in items  # already-selected columns excluded

def test_columns_completion_prefix_filter(self, sample_db):
    ...
    items = [c.value for c in param.type.shell_complete(ctx, param, "na")]
    assert "name" in items
    assert "language" not in items
```

### Task 1.2: `OrderType` for `--order`

**Files:**
- Modify: `src/sqlflag/cli.py` (add `OrderType` at module scope, wire into `_make_table_command`)

**Implementation:**

```python
class OrderType(click.ParamType):
    """Column name for ORDER BY, optionally prefixed with '-' for DESC."""

    name = "order_spec"

    def __init__(self, columns: list[str]):
        self._columns = columns

    def convert(self, value, param, ctx):
        return value

    def shell_complete(self, ctx, param, incomplete):
        if incomplete.startswith("-"):
            prefix = "-"
            stem = incomplete[1:]
        else:
            prefix = ""
            stem = incomplete
        items = []
        for col in self._columns:
            if col.startswith(stem):
                items.append(CompletionItem(prefix + col))
        return items
```

**Wire-up:**
```python
click.Option(
    ["--order"], multiple=True,
    type=OrderType(all_column_names),
    help="ORDER BY column. Prefix with - for DESC.",
),
```

**Tests:**

```python
def test_order_completion_asc(self, sample_db):
    ...
    items = [c.value for c in param.type.shell_complete(ctx, param, "")]
    assert "name" in items
    assert "-name" not in items  # not shown until user types '-'

def test_order_completion_desc(self, sample_db):
    ...
    items = [c.value for c in param.type.shell_complete(ctx, param, "-")]
    assert "-name" in items
    assert "-language" in items
```

### Task 1.3: Smoke-test subcommand and flag-name completion

**Files:**
- New test: `tests/test_completion.py`

Use Click's `click.shell_completion.ShellComplete` or directly invoke the `BashComplete.complete()` method with mocked env vars. This verifies the lazy-group approach is compatible with Click's completion driver.

```python
from click.shell_completion import ShellComplete, BashComplete

def test_subcommand_completion(sample_db, tmp_path):
    from sqlflag.__main__ import main
    # Click's bash_complete class can be instantiated and asked for completions
    comp = BashComplete(main, {}, "sqlflag", "_SQLFLAG_COMPLETE")
    # Simulate: user typed "sqlflag <sample_db> re" and hit TAB
    completions = comp.get_completions(
        args=[sample_db],
        incomplete="re",
    )
    names = [c.value for c in completions]
    assert "repos" in names
```

(The exact API call may need fixups; Click's completion harness has shifted across minor versions. Use whatever shape `BashComplete.complete()` or `_resolve_completion()` exposes in the installed Click version.)

---

## Phase 2: Tier 2 (operator-aware) completion

### Task 2.1: `FilterValueType` with operator completion

**Files:**
- Modify: `src/sqlflag/cli.py` (add `FilterValueType`, wire into per-column `click.Option` in `_make_table_command`)

**Implementation:**

```python
class FilterValueType(click.ParamType):
    """A filter value that accepts `[op:]value`. Completes operators for this column's type."""

    name = "filter_value"

    def __init__(self, operators: list[str]):
        self._operators = operators

    def convert(self, value, param, ctx):
        return value

    def shell_complete(self, ctx, param, incomplete):
        items = []
        for op in self._operators:
            prefix = f"{op}:"
            if prefix.startswith(incomplete):
                items.append(CompletionItem(prefix))
        # Also offer `null` since it's a reserved literal value
        if "null".startswith(incomplete):
            items.append(CompletionItem("null"))
        return items
```

**Wire-up (replace the current flag-building loop):**

```python
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
            type=FilterValueType(ops),
            help=help_text,
        )
    )
```

**Tests (new `TestCompletionTier2`):**

```python
def test_numeric_column_offers_gt_lt_not(self, sample_db):
    app = SqlFlag(sample_db)
    cmd = app.click_app.commands["repos"]
    param = next(p for p in cmd.params if p.name == "stars")
    ctx = click.Context(cmd)
    items = [c.value for c in param.type.shell_complete(ctx, param, "")]
    assert "gt:" in items
    assert "lt:" in items
    assert "not:" in items
    assert "contains:" not in items  # inappropriate for INTEGER

def test_text_column_offers_contains_not(self, sample_db):
    ...
    assert "contains:" in items
    assert "not:" in items
    assert "gt:" not in items

def test_datetime_column_offers_since_before_not(self, sample_db):
    ...
    assert "since:" in items
    assert "before:" in items
    assert "not:" in items

def test_operator_prefix_filter(self, sample_db):
    ...
    items = [c.value for c in param.type.shell_complete(ctx, param, "g")]
    assert "gt:" in items
    assert "lt:" not in items  # doesn't start with 'g'

def test_null_offered(self, sample_db):
    ...
    items = [c.value for c in param.type.shell_complete(ctx, param, "n")]
    assert "not:" in items
    assert "null" in items
```

---

## Phase 3: Tier 3 (data-aware, opt-in) completion

### Task 3.1: Extend `FilterValueType` with distinct-value completion

**Files:**
- Modify: `src/sqlflag/cli.py` (`FilterValueType` gets `table_name`, `column_name`, `engine` attributes)
- Modify: `src/sqlflag/query.py` (add `QueryEngine.distinct_values(table, column, limit)`)

**Env-var gate:** `SQLFLAG_COMPLETE_VALUES=1` enables value completion. Default off. Rationale: value completion runs SQL on every TAB press, which is surprising to first-time users; better as opt-in so the default behavior stays fast and predictable.

**Cardinality gate:** if `SELECT COUNT(DISTINCT col) FROM tab` returns > `SQLFLAG_VALUE_COMPLETE_MAX` (default 100), skip value completion for that column. Cheap query (SQLite's query planner short-circuits on indexed columns).

**Implementation:**

```python
# src/sqlflag/query.py
class QueryEngine:
    # ... existing code ...

    def distinct_values(self, table: str, column: str, limit: int = 100) -> list[str]:
        sql = f"SELECT DISTINCT [{column}] FROM [{table}] WHERE [{column}] IS NOT NULL LIMIT ?"
        rows = self._db.execute(sql, (limit + 1,)).fetchall()
        return [str(r[0]) for r in rows]

    def distinct_count(self, table: str, column: str) -> int:
        sql = f"SELECT COUNT(DISTINCT [{column}]) FROM [{table}]"
        return self._db.execute(sql).fetchone()[0]
```

```python
# src/sqlflag/cli.py
import os

class FilterValueType(click.ParamType):
    name = "filter_value"

    def __init__(self, operators, table_name=None, column_name=None, engine=None):
        self._operators = operators
        self._table = table_name
        self._column = column_name
        self._engine = engine

    def convert(self, value, param, ctx):
        return value

    def shell_complete(self, ctx, param, incomplete):
        items = []
        # Operator prefixes (always)
        for op in self._operators:
            prefix = f"{op}:"
            if prefix.startswith(incomplete):
                items.append(CompletionItem(prefix))
        if "null".startswith(incomplete):
            items.append(CompletionItem("null"))
        # Distinct values (opt-in, bounded)
        if self._should_complete_values(incomplete):
            try:
                max_card = int(os.environ.get("SQLFLAG_VALUE_COMPLETE_MAX", "100"))
                count = self._engine.distinct_count(self._table, self._column)
                if count <= max_card:
                    for val in self._engine.distinct_values(self._table, self._column, limit=max_card):
                        if val.startswith(incomplete):
                            items.append(CompletionItem(val))
            except Exception:
                pass  # completion must never error; degrade silently
        return items

    def _should_complete_values(self, incomplete):
        if not os.environ.get("SQLFLAG_COMPLETE_VALUES"):
            return False
        if self._engine is None or self._table is None or self._column is None:
            return False
        # Skip if user is typing an operator prefix
        for op in self._operators:
            if incomplete.startswith(f"{op}:"):
                return False
        return True
```

**Wire-up (updated `_make_table_command`):**

```python
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
```

### Task 3.2: Tests for Tier 3

```python
class TestCompletionTier3:
    def test_values_off_by_default(self, sample_db, monkeypatch):
        monkeypatch.delenv("SQLFLAG_COMPLETE_VALUES", raising=False)
        app = SqlFlag(sample_db)
        cmd = app.click_app.commands["repos"]
        param = next(p for p in cmd.params if p.name == "language")
        ctx = click.Context(cmd)
        items = [c.value for c in param.type.shell_complete(ctx, param, "")]
        assert "python" not in items  # data values NOT offered by default
        assert "contains:" in items   # operators still offered

    def test_values_on_with_env(self, sample_db, monkeypatch):
        monkeypatch.setenv("SQLFLAG_COMPLETE_VALUES", "1")
        ...
        items = [c.value for c in param.type.shell_complete(ctx, param, "")]
        assert "python" in items
        assert "go" in items
        assert "contains:" in items  # operators alongside values

    def test_values_prefix_filter(self, sample_db, monkeypatch):
        monkeypatch.setenv("SQLFLAG_COMPLETE_VALUES", "1")
        ...
        items = [c.value for c in param.type.shell_complete(ctx, param, "py")]
        assert "python" in items
        assert "go" not in items

    def test_cardinality_gate_skips_high_cardinality(self, sample_db, monkeypatch):
        # sample_db has only 4 rows; artificially lower the threshold to 2
        monkeypatch.setenv("SQLFLAG_COMPLETE_VALUES", "1")
        monkeypatch.setenv("SQLFLAG_VALUE_COMPLETE_MAX", "2")
        ...
        # repos.name has 4 distinct values > 2 threshold
        items = [c.value for c in param.type.shell_complete(ctx, param, "")]
        # No data values returned
        assert "alpha" not in items
        assert "beta" not in items
        # Operators still work
        assert "contains:" in items

    def test_skip_values_when_typing_operator(self, sample_db, monkeypatch):
        monkeypatch.setenv("SQLFLAG_COMPLETE_VALUES", "1")
        ...
        items = [c.value for c in param.type.shell_complete(ctx, param, "gt:")]
        # Once user has committed to an operator, don't pollute with distinct values
        assert not any(c in items for c in ["python", "go"])

    def test_completion_never_raises(self, sample_db, monkeypatch):
        """Completion errors must degrade silently. A broken DB connection should not crash the shell."""
        monkeypatch.setenv("SQLFLAG_COMPLETE_VALUES", "1")
        app = SqlFlag(sample_db)
        cmd = app.click_app.commands["repos"]
        param = next(p for p in cmd.params if p.name == "language")
        # Sabotage the engine
        param.type._engine = None
        ctx = click.Context(cmd)
        # Must not raise
        items = param.type.shell_complete(ctx, param, "")
        assert "contains:" in [c.value for c in items]  # operators still work
```

### Task 3.3: Document the env-var knobs

**Files:**
- Modify: `docs/superpowers/specs/2026-03-17-sqlflag-design.md` (see Phase 4)
- Modify: `CLAUDE.md` (brief mention)

---

## Phase 4: Install UX and docs

### Task 4.1: Add `sqlflag completion <shell>` helper

**Why a dedicated subcommand:** Click supports `_SQLFLAG_COMPLETE=bash_source sqlflag` out of the box, but that's opaque to users who don't read Click docs. A first-class `sqlflag completion bash` subcommand is discoverable from `sqlflag --help`.

**Complication:** the top-level lazy group takes `db_path` as its required-ish argument. A `completion` subcommand that doesn't need a db path is awkward there. Two shapes to choose from:

**Option A: `sqlflag completion <shell>`** as a peer subcommand of `db_path`. Requires `db_path` to be truly optional and to early-exit in the top-level `main` when the next token is `completion`.

**Option B: `sqlflag --install-completion <shell>`** as a top-level flag. Simpler: no command-tree gymnastics.

**Recommendation:** Option B for simplicity. Implementation:

```python
# In __main__.py main():
@click.option(
    "--install-completion",
    type=click.Choice(["bash", "zsh", "fish"]),
    default=None,
    help="Print shell-completion source for the given shell, then exit.",
)
def main(ctx, db_path, install_completion):
    if install_completion is not None:
        _print_completion_snippet(install_completion)
        ctx.exit(0)
    # ... rest of main ...

def _print_completion_snippet(shell: str) -> None:
    import subprocess
    # Invoke Click's own generator by setting the env var
    env = {"_SQLFLAG_COMPLETE": f"{shell}_source"}
    # Actually, the cleanest way is to delegate to click.shell_completion directly
    from click.shell_completion import shell_complete
    # Or invoke ourselves:
    click.echo(subprocess.check_output(
        ["sqlflag"], env={**os.environ, **env}
    ).decode())
```

The simplest reliable implementation is actually to just print the canonical install command and let the user run it, because Click's own machinery emits the source script when invoked with `_SQLFLAG_COMPLETE=<shell>_source`. A friendly printout:

```python
def _print_completion_snippet(shell: str) -> None:
    msg = {
        "bash": 'eval "$(_SQLFLAG_COMPLETE=bash_source sqlflag)"',
        "zsh":  'eval "$(_SQLFLAG_COMPLETE=zsh_source sqlflag)"',
        "fish": '_SQLFLAG_COMPLETE=fish_source sqlflag | source',
    }[shell]
    click.echo(f"# Add this to your shell config (e.g., ~/.bashrc):\n{msg}")
```

This avoids needing to replicate Click's source-generation and keeps us forward-compatible with Click upgrades.

**Test:**

```python
def test_install_completion_bash():
    runner = CliRunner()
    result = runner.invoke(main, ["--install-completion", "bash"])
    assert result.exit_code == 0
    assert "_SQLFLAG_COMPLETE=bash_source" in result.output

def test_install_completion_invalid_shell():
    runner = CliRunner()
    result = runner.invoke(main, ["--install-completion", "tcsh"])
    assert result.exit_code != 0  # Click rejects invalid Choice
```

### Task 4.2: Update spec with Shell Completion section

**File:** `docs/superpowers/specs/2026-03-17-sqlflag-design.md`

Add a new top-level section after "Output Formatting". Draft content:

```markdown
## Shell Completion

sqlflag ships with shell completion for bash, zsh, and fish, derived from the
database schema and (optionally) its data.

### Installation

    # bash
    eval "$(_SQLFLAG_COMPLETE=bash_source sqlflag)"

    # zsh
    eval "$(_SQLFLAG_COMPLETE=zsh_source sqlflag)"

    # fish
    _SQLFLAG_COMPLETE=fish_source sqlflag | source

Or run `sqlflag --install-completion <shell>` to print the one-liner.

### What gets completed

| Scope | Completed tokens | Source |
|-------|------------------|--------|
| Positional 1 | file paths | Click default for `click.Path` |
| Subcommand | table/view names, `sql`, `schema` | `SchemaInfo.queryable_names()` |
| Flag name | `--language`, `--stars`, etc. | `SchemaInfo.flaggable_columns()` |
| `--format` | `table`, `json`, `csv` | `click.Choice` |
| `--columns` | remaining columns (comma-aware) | `ColumnListType` |
| `--order` | column names, with optional `-` prefix | `OrderType` |
| Filter value (Tier 2) | operator prefixes by column type | `FilterValueType` |
| Filter value (Tier 3, opt-in) | distinct column values | `FilterValueType` + `QueryEngine` |

### Tier 3: value completion (opt-in)

Distinct-value completion is off by default because it issues SQL on every TAB
press. Enable with:

    export SQLFLAG_COMPLETE_VALUES=1

Bounded by cardinality. Columns with more than 100 distinct values
(configurable via `SQLFLAG_VALUE_COMPLETE_MAX`) skip value completion to keep
latency predictable.

Completion never raises: if the database cannot be opened, if a query fails,
if any internal error occurs, completion degrades silently and the shell
behaves as if no completions were available.
```

### Task 4.3: Update CLAUDE.md

**File:** `CLAUDE.md`

Add after the "Key design decisions" bullets:

```markdown
- **Shell completion is schema- and data-aware.** Completion hooks live in
  custom `ParamType` subclasses (`ColumnListType`, `OrderType`,
  `FilterValueType`) in `cli.py`. Tier 3 value completion is gated by
  `SQLFLAG_COMPLETE_VALUES=1` and a cardinality ceiling to keep TAB latency
  bounded.
```

---

## Test strategy

### Unit tests
Direct invocation of `ParamType.shell_complete(ctx, param, incomplete)`. Fast, no shell required, no subprocess overhead. Every Tier-1/2/3 case covered this way.

### Integration test (one per phase)
Use `click.shell_completion.BashComplete` directly to verify the full completion pipeline works end-to-end. Not a subprocess test (still in-process, still fast).

### Manual smoke test (per phase)
```bash
pip install -e .
eval "$(_SQLFLAG_COMPLETE=bash_source sqlflag)"
sqlflag ~/.repoindex/index.db <TAB>
sqlflag ~/.repoindex/index.db repos --<TAB>
sqlflag ~/.repoindex/index.db repos --format <TAB>
sqlflag ~/.repoindex/index.db repos --columns <TAB>
sqlflag ~/.repoindex/index.db repos --stars <TAB>
export SQLFLAG_COMPLETE_VALUES=1
sqlflag ~/.repoindex/index.db repos --language <TAB>
```

This is documented in the plan but not automated; shell-completion tests in CI would require wrapping bash/zsh/fish subprocesses, which is flaky on CI and low ROI given that in-process tests cover the same logic.

### Coverage

Run `pytest tests/ --cov=sqlflag --cov-report=term-missing` after each phase. Target: 100% coverage on new completion code paths, accepting that some `except Exception: pass` lines in Tier 3 remain uncovered (they exist precisely to not surface errors and are hard to exercise without a broken DB fixture).

---

## Rollout and risk

### Phase dependencies
Phase 0 unlocks everything else. Phases 1, 2, 3 can ship as separate commits; Phase 4 (docs + install helper) can ship alongside 1 or after 3.

### Rollback
Each phase is independently revertable. Phase 0 is the only one with architectural implications; if the lazy-group approach turns out to have a subtle Click-version issue, we can revert and keep the current `sys.argv` splitter while we investigate. Phases 1-3 are pure additions that don't change runtime behavior of non-completion code paths.

### Known unknowns
- **Click version sensitivity.** Click 8.0 changed the completion API; Click 8.1 added more. We target `click>=8` in pyproject.toml today. Phase 0 should pin to `click>=8.1` if the lazy-group + completion combo requires it. Verify during Phase 0.
- **Shell behavior on values with spaces.** Values like `--language "Ada Lovelace"` may need quoting in completion output. Click's `CompletionItem` handles this on most shells but fish has quirks. Covered by manual smoke test.
- **`repoindex` integration.** None. We removed all mount code; repoindex is a consumer of sqlflag as a standalone CLI only. Shell completion affects the `sqlflag` binary only, not any library consumer.

### Success criteria
- All three tiers demonstrable with the manual smoke test above.
- Full test suite passes with new tests added.
- `sqlflag --install-completion bash` prints the canonical install line.
- Spec updated with a single Shell Completion section.
- No regression in existing 97 tests plus 8 new entry-point tests from Phase 0.

---

## Estimated scope

- **Phase 0:** ~1 file rewrite (`__main__.py`), ~1 test class (~60 lines), ~30 minutes.
- **Phase 1:** two small ParamType classes (~40 lines), wire-up (~4 lines in `_make_table_command`), tests (~80 lines), ~45 minutes.
- **Phase 2:** one ParamType (~30 lines), wire-up (replace existing `click.Option` construction, ~5 lines), tests (~100 lines), ~45 minutes.
- **Phase 3:** extend FilterValueType (~40 lines), two QueryEngine methods (~10 lines), env-var gating + cardinality gate (~15 lines), tests (~100 lines), ~60 minutes.
- **Phase 4:** install helper (~15 lines), spec section (~50 lines markdown), CLAUDE.md update (~5 lines), ~30 minutes.

**Total:** ~3.5 hours of focused work. Realistic with buffer for Click quirks and test-debugging: ~1 day.
