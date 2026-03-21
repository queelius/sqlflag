# Code Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 2 critical bugs, 2 important issues, and 5 simplifications found during code review.

**Architecture:** Independent fixes across parser, query engine, CLI, and config. Each task is self-contained.

**Tech Stack:** Python, SQLite, Click, pytest

---

### Task 1: Fix FTS search + filter parameter order bug (CRITICAL)

**Files:**
- Modify: `src/sqlflag/query.py:32-34`
- Test: `tests/test_query.py` (new test), `tests/test_cli.py` (new test)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_query.py` in `TestSearch`:

```python
def test_fts_search_with_filter(self, sample_db_with_fts):
    engine = QueryEngine(sample_db_with_fts)
    rows = engine.query("repos", filters={"language": ["python"]}, search="alpha")
    assert len(rows) == 1
    assert rows[0]["name"] == "alpha"
```

Add to `tests/test_cli.py` in `TestSearchCommand`:

```python
def test_fts_search_with_filter(self, sample_db_with_fts):
    app = SqlFlag(sample_db_with_fts)
    runner = CliRunner()
    result = runner.invoke(app.click_app, [
        "repos", "--language", "python", "--search", "alpha", "--format", "json",
    ])
    assert result.exit_code == 0, result.output
    rows = [json.loads(line) for line in result.output.strip().split("\n")]
    assert len(rows) == 1
    assert rows[0]["name"] == "alpha"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_query.py::TestSearch::test_fts_search_with_filter tests/test_cli.py::TestSearchCommand::test_fts_search_with_filter -v`
Expected: FAIL (wrong results due to parameter order)

- [ ] **Step 3: Fix parameter order**

In `src/sqlflag/query.py`, change line 34 from `params.append(search)` to `params.insert(0, search)`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_query.py::TestSearch tests/test_cli.py::TestSearchCommand -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sqlflag/query.py tests/test_query.py tests/test_cli.py
git commit -m "fix: FTS search parameter order when combined with column filters"
```

---

### Task 2: Fix unquoted column names in SQL fragments (CRITICAL)

**Files:**
- Modify: `src/sqlflag/parser.py:57-71,74-99` (bracket-quote column in all SQL fragments)
- Modify: `src/sqlflag/query.py:92` (bracket-quote column in IN clause)
- Test: `tests/test_query.py` (new tests)

- [ ] **Step 1: Write failing test**

Add a fixture to `tests/conftest.py`:

```python
@pytest.fixture
def reserved_word_db(tmp_path):
    """Database with a column named 'group' (SQLite reserved word)."""
    db_path = str(tmp_path / "reserved.db")
    db = Database(db_path)
    db.execute('CREATE TABLE items (id INTEGER, "group" TEXT, value INTEGER)')
    db["items"].insert_all([
        {"id": 1, "group": "a", "value": 10},
        {"id": 2, "group": "b", "value": 20},
        {"id": 3, "group": "a", "value": 30},
    ])
    return db_path
```

Add to `tests/test_query.py`:

```python
class TestReservedWordColumns:
    def test_equality_filter_on_reserved_word(self, reserved_word_db):
        engine = QueryEngine(reserved_word_db)
        rows = engine.query("items", filters={"group": ["a"]})
        assert len(rows) == 2

    def test_operator_filter_on_reserved_word(self, reserved_word_db):
        engine = QueryEngine(reserved_word_db)
        rows = engine.query("items", filters={"group": ["not:a"]})
        assert len(rows) == 1
        assert rows[0]["group"] == "b"

    def test_in_clause_on_reserved_word(self, reserved_word_db):
        engine = QueryEngine(reserved_word_db)
        rows = engine.query("items", filters={"group": ["a", "b"]})
        assert len(rows) == 3
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_query.py::TestReservedWordColumns -v`
Expected: FAIL with `OperationalError: near "group": syntax error`

- [ ] **Step 3: Bracket-quote column names**

In `src/sqlflag/parser.py`, change all `{column}` references in SQL fragments to `[{column}]`:

- Line 67: `f"{column} IS NULL"` becomes `f"[{column}] IS NULL"`
- Line 71: `f"{column} = ?"` becomes `f"[{column}] = ?"`
- Line 77: `f"{column} IS NOT NULL"` becomes `f"[{column}] IS NOT NULL"`
- Line 79: `f"{column} != ?"` becomes `f"[{column}] != ?"`
- Line 83: `f"{column} > ?"` becomes `f"[{column}] > ?"`
- Line 87: `f"{column} < ?"` becomes `f"[{column}] < ?"`
- Line 91: `f"{column} LIKE ? ESCAPE '\\'"` becomes `f"[{column}] LIKE ? ESCAPE '\\'"`
- Line 95: `f"{column} >= ?"` becomes `f"[{column}] >= ?"`
- Line 99: `f"{column} < ?"` becomes `f"[{column}] < ?"`

In `src/sqlflag/query.py`, line 92:
- `f"{col_name} IN ({placeholders})"` becomes `f"[{col_name}] IN ({placeholders})"`

- [ ] **Step 4: Run tests**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/sqlflag/parser.py src/sqlflag/query.py tests/conftest.py tests/test_query.py
git commit -m "fix: bracket-quote column names in SQL fragments for reserved word safety"
```

---

### Task 3: Move typer to optional dependencies

**Files:**
- Modify: `pyproject.toml:18-22,24-28`

- [ ] **Step 1: Update pyproject.toml**

Move `"typer>=0.9"` from `dependencies` to `[project.optional-dependencies]`:

```toml
dependencies = [
    "sqlite-utils>=3.35",
    "rich>=13",
]

[project.optional-dependencies]
typer = ["typer>=0.9"]
dev = [
    "pytest>=7",
    "pytest-cov",
    "typer>=0.9",
]
```

- [ ] **Step 2: Reinstall and run tests**

Run: `pip install -e ".[dev]" && pytest tests/ -v`
Expected: All PASS (dev includes typer)

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "fix: move typer to optional dependency"
```

---

### Task 4: Share SchemaInfo between SqlFlag and QueryEngine

**Files:**
- Modify: `src/sqlflag/query.py:9-15`
- Modify: `src/sqlflag/cli.py:20-21`

- [ ] **Step 1: Update QueryEngine to accept optional SchemaInfo**

In `src/sqlflag/query.py`, change `__init__`:

```python
def __init__(self, db_path: str, schema: SchemaInfo | None = None):
    self._db_path = db_path
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    self._db = Database(conn)
    self._schema = schema or SchemaInfo(db_path)
```

- [ ] **Step 2: Pass SchemaInfo from SqlFlag**

In `src/sqlflag/cli.py`, change line 21:

```python
self._engine = QueryEngine(db_path, schema=self._schema)
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/sqlflag/query.py src/sqlflag/cli.py
git commit -m "refactor: share SchemaInfo instance between SqlFlag and QueryEngine"
```

---

### Task 5: Simplify OPERATORS to frozenset and remove dead code

**Files:**
- Modify: `src/sqlflag/parser.py:6-13,101-102`
- Modify: `src/sqlflag/query.py:69-74`

- [ ] **Step 1: Change OPERATORS to frozenset**

In `src/sqlflag/parser.py`, replace lines 6-13:

```python
OPERATORS = frozenset({"not", "gt", "lt", "contains", "since", "before"})
```

- [ ] **Step 2: Remove dead fallthrough**

In `src/sqlflag/parser.py`, remove lines 101-102 (the unreachable equality fallback in `_apply_operator`).

- [ ] **Step 3: Extract `has_operator_prefix` helper**

Add to `src/sqlflag/parser.py` after OPERATORS:

```python
def has_operator_prefix(value: str) -> bool:
    return any(value.startswith(op + ":") for op in OPERATORS)
```

- [ ] **Step 4: Use helper in query.py**

In `src/sqlflag/query.py`, replace lines 69-74:

```python
for v in values:
    if v == "null" or has_operator_prefix(v):
```

Update import on line 5:

```python
from sqlflag.parser import parse_value, _coerce_value, OPERATORS, has_operator_prefix
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/sqlflag/parser.py src/sqlflag/query.py
git commit -m "refactor: simplify OPERATORS to frozenset, extract has_operator_prefix, remove dead code"
```

---

### Task 6: Remove unnecessary list() wrapper and unused search method

**Files:**
- Modify: `src/sqlflag/cli.py:129`
- Modify: `src/sqlflag/query.py:53-54`
- Modify: `tests/test_query.py:115-120`

- [ ] **Step 1: Remove list() wrapper**

In `src/sqlflag/cli.py`, change line 129 from `rows = list(engine.query(` to `rows = engine.query(`.

- [ ] **Step 2: Remove QueryEngine.search()**

In `src/sqlflag/query.py`, delete lines 53-54 (the `search` method).

- [ ] **Step 3: Remove search test**

In `tests/test_query.py`, delete the `TestSearch::test_fts_search` method (lines 116-120). The FTS tests in Task 1 cover the query-based search path.

- [ ] **Step 4: Run tests**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/sqlflag/cli.py src/sqlflag/query.py tests/test_query.py
git commit -m "refactor: remove unnecessary list() wrapper and unused QueryEngine.search()"
```
