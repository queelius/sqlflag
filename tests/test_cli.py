import json

import pytest
from click.testing import CliRunner
from sqlflag.cli import SqlFlag


class TestQueryCommands:
    def test_query_all_rows(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, ["repos", "--format", "json"])
        assert result.exit_code == 0, result.output
        lines = result.output.strip().split("\n")
        assert len(lines) == 4

    def test_query_equality_filter(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "repos", "--language", "python", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert len(rows) == 2
        assert all(r["language"] == "python" for r in rows)

    def test_query_operator_filter(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "repos", "--stars", "gt:75", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert all(r["stars"] > 75 for r in rows)

    def test_query_multiple_values_in(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "repos",
            "--language", "python", "--language", "go",
            "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert len(rows) == 3

    def test_query_order(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "repos", "--order", "-stars", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert rows[0]["stars"] >= rows[-1]["stars"]

    def test_query_limit(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "repos", "--limit", "2", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        lines = result.output.strip().split("\n")
        assert len(lines) == 2

    def test_query_columns(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "repos", "--columns", "name,stars", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        row = json.loads(result.output.strip().split("\n")[0])
        assert set(row.keys()) == {"name", "stars"}

    def test_query_any_mode(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "repos",
            "--language", "go", "--stars", "gt:150",
            "--any", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert len(rows) == 2  # beta (go) + gamma (stars>150)

    def test_query_view(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "active_repos", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert all(r["is_archived"] == 0 for r in rows)

    def test_query_contains(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "repos", "--name", "contains:lph", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert len(rows) == 1
        assert rows[0]["name"] == "alpha"

    def test_hyphenated_flag(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "repos", "--created-at", "since:2025-01-01", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert len(rows) == 2


class TestTableAllowlist:
    def test_only_allowed_tables(self, sample_db):
        app = SqlFlag(sample_db, tables=["repos"])
        runner = CliRunner()
        result = runner.invoke(app.click_app, ["repos", "--format", "json"])
        assert result.exit_code == 0
        result = runner.invoke(app.click_app, ["events", "--format", "json"])
        assert result.exit_code != 0


class TestDefaultColumns:
    def test_default_columns_applied(self, sample_db):
        app = SqlFlag(sample_db, default_columns={"repos": ["name", "stars"]})
        runner = CliRunner()
        result = runner.invoke(app.click_app, ["repos", "--format", "json"])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert set(rows[0].keys()) == {"name", "stars"}

    def test_explicit_columns_override_default(self, sample_db):
        app = SqlFlag(sample_db, default_columns={"repos": ["name", "stars"]})
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "repos", "--columns", "name,language", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert set(rows[0].keys()) == {"name", "language"}

    def test_no_default_columns_returns_all(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, ["repos", "--format", "json"])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert len(rows[0].keys()) == 6  # all columns in repos


class TestSqlCommand:
    def test_raw_sql(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "sql", "SELECT name FROM repos WHERE stars > 100", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert len(rows) == 1
        assert rows[0]["name"] == "gamma"


class TestSchemaCommand:
    def test_schema_overview(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, ["schema"])
        assert result.exit_code == 0
        assert "repos" in result.output
        assert "events" in result.output

    def test_schema_table_detail(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, ["schema", "repos"])
        assert result.exit_code == 0
        assert "name" in result.output
        assert "stars" in result.output
        assert "INTEGER" in result.output

    def test_schema_shows_fts(self, sample_db_with_fts):
        app = SqlFlag(sample_db_with_fts)
        runner = CliRunner()
        result = runner.invoke(app.click_app, ["schema", "repos"])
        assert result.exit_code == 0
        assert "yes" in result.output.lower()


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


class TestSearchCommand:
    def test_fts_search(self, sample_db_with_fts):
        app = SqlFlag(sample_db_with_fts)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "repos", "--search", "alpha", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert any(r["name"] == "alpha" for r in rows)

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


class TestEntryPoint:
    """The standalone `sqlflag <db_path> ...` entry point (SqlFlagGroup lazy group)."""

    def test_no_args_shows_help(self):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        assert "sqlflag" in result.output.lower()
        assert "usage:" in result.output.lower()

    def test_help_flag_without_db(self):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "usage:" in result.output.lower()

    def test_db_path_lists_subcommands(self, sample_db):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, [sample_db, "--help"])
        assert result.exit_code == 0, result.output
        assert "repos" in result.output
        assert "events" in result.output
        assert "sql" in result.output
        assert "schema" in result.output

    def test_db_then_table_runs_query(self, sample_db):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, [sample_db, "repos", "--format", "json"])
        assert result.exit_code == 0, result.output
        lines = [ln for ln in result.output.strip().split("\n") if ln]
        assert len(lines) == 4  # sample_db has 4 repos

    def test_db_then_sql(self, sample_db):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(
            main,
            [sample_db, "sql", "SELECT count(*) as n FROM repos", "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        import json as _json
        row = _json.loads(result.output.strip())
        assert row["n"] == 4

    def test_db_then_schema(self, sample_db):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, [sample_db, "schema"])
        assert result.exit_code == 0, result.output
        assert "repos" in result.output

    def test_nonexistent_db_errors(self):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, ["/tmp/this-db-does-not-exist-xyz.db", "repos"])
        assert result.exit_code != 0

    def test_table_help_shows_column_flags(self, sample_db):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, [sample_db, "repos", "--help"])
        assert result.exit_code == 0, result.output
        assert "--language" in result.output
        assert "--stars" in result.output


class TestCompletionTier1:
    """Shell completion for --columns (comma-aware) and --order (- prefix)."""

    def _param(self, app, table, name):
        import click
        cmd = app.click_app.commands[table]
        param = next(p for p in cmd.params if p.name == name)
        ctx = click.Context(cmd)
        return ctx, param

    def test_columns_completion_empty_offers_all(self, sample_db):
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "columns")
        items = [c.value for c in param.type.shell_complete(ctx, param, "")]
        for col in ("name", "language", "stars", "description", "created_at"):
            assert col in items, f"expected column {col} in {items}"

    def test_columns_completion_prefix_filter(self, sample_db):
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "columns")
        items = [c.value for c in param.type.shell_complete(ctx, param, "na")]
        assert "name" in items
        assert "language" not in items  # doesn't start with 'na'

    def test_columns_completion_after_comma(self, sample_db):
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "columns")
        items = [c.value for c in param.type.shell_complete(ctx, param, "name,")]
        assert "name,language" in items
        assert "name,stars" in items
        assert "name,name" not in items  # already-selected column not offered

    def test_columns_completion_after_comma_with_prefix(self, sample_db):
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "columns")
        items = [c.value for c in param.type.shell_complete(ctx, param, "name,la")]
        assert "name,language" in items
        assert "name,stars" not in items  # doesn't start with 'la'
        assert "name,name" not in items

    def test_columns_completion_multiple_already_selected(self, sample_db):
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "columns")
        items = [c.value for c in param.type.shell_complete(ctx, param, "name,language,")]
        assert "name,language,stars" in items
        assert "name,language,name" not in items
        assert "name,language,language" not in items

    def test_order_completion_empty_offers_asc(self, sample_db):
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "order")
        items = [c.value for c in param.type.shell_complete(ctx, param, "")]
        assert "name" in items
        assert "language" in items
        # Descending (-) only shown once user types '-'
        assert "-name" not in items

    def test_order_completion_dash_prefix_offers_desc(self, sample_db):
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "order")
        items = [c.value for c in param.type.shell_complete(ctx, param, "-")]
        assert "-name" in items
        assert "-language" in items
        assert "-stars" in items
        assert "name" not in items  # when user typed '-', only desc candidates

    def test_order_completion_prefix_filter(self, sample_db):
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "order")
        items = [c.value for c in param.type.shell_complete(ctx, param, "na")]
        assert "name" in items
        assert "language" not in items

    def test_order_completion_dash_prefix_filter(self, sample_db):
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "order")
        items = [c.value for c in param.type.shell_complete(ctx, param, "-st")]
        assert "-stars" in items
        assert "-name" not in items


class TestCompletionIntegrationTier1:
    """Drive Click's BashComplete end-to-end to prove wiring from the top-level group."""

    def test_subcommand_completion(self, sample_db):
        from click.shell_completion import BashComplete
        from sqlflag.__main__ import main
        comp = BashComplete(main, {}, "sqlflag", "_SQLFLAG_COMPLETE")
        items = [c.value for c in comp.get_completions(args=[sample_db], incomplete="re")]
        assert "repos" in items

    def test_flag_name_completion(self, sample_db):
        from click.shell_completion import BashComplete
        from sqlflag.__main__ import main
        comp = BashComplete(main, {}, "sqlflag", "_SQLFLAG_COMPLETE")
        items = [c.value for c in comp.get_completions(args=[sample_db, "repos"], incomplete="--lan")]
        assert "--language" in items

    def test_format_choice_completion(self, sample_db):
        from click.shell_completion import BashComplete
        from sqlflag.__main__ import main
        comp = BashComplete(main, {}, "sqlflag", "_SQLFLAG_COMPLETE")
        items = [c.value for c in comp.get_completions(
            args=[sample_db, "repos", "--format"], incomplete=""
        )]
        for fmt in ("table", "json", "csv"):
            assert fmt in items

    def test_columns_value_completion(self, sample_db):
        from click.shell_completion import BashComplete
        from sqlflag.__main__ import main
        comp = BashComplete(main, {}, "sqlflag", "_SQLFLAG_COMPLETE")
        items = [c.value for c in comp.get_completions(
            args=[sample_db, "repos", "--columns"], incomplete="na"
        )]
        assert "name" in items

    def test_order_value_completion_bare_column(self, sample_db):
        """
        Ascending-order completion (plain column names) works through BashComplete.
        The `-prefix` DESC form is not tab-completable through Click because `-`
        is indistinguishable from a new option flag at the shell level; users
        type `--order -column` manually at runtime. OrderType.shell_complete is
        still unit-tested for the `-` case in case Click's dispatch changes.
        """
        from click.shell_completion import BashComplete
        from sqlflag.__main__ import main
        comp = BashComplete(main, {}, "sqlflag", "_SQLFLAG_COMPLETE")
        items = [c.value for c in comp.get_completions(
            args=[sample_db, "repos", "--order"], incomplete="na"
        )]
        assert "name" in items


class TestCompletionTier2:
    """Operator-prefix completion on column filter flags (schema-aware)."""

    def _param(self, app, table, col_flag):
        import click
        cmd = app.click_app.commands[table]
        param = next(p for p in cmd.params if p.name == col_flag)
        ctx = click.Context(cmd)
        return ctx, param

    def test_text_column_offers_not_contains(self, sample_db):
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "language")
        items = [c.value for c in param.type.shell_complete(ctx, param, "")]
        assert "not:" in items
        assert "contains:" in items
        assert "gt:" not in items  # not appropriate for TEXT
        assert "lt:" not in items
        assert "since:" not in items

    def test_integer_column_offers_not_gt_lt(self, sample_db):
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "stars")
        items = [c.value for c in param.type.shell_complete(ctx, param, "")]
        assert "not:" in items
        assert "gt:" in items
        assert "lt:" in items
        assert "contains:" not in items  # not appropriate for INTEGER
        assert "since:" not in items

    def test_boolean_column_offers_not_only(self, sample_db):
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "is_archived")
        items = [c.value for c in param.type.shell_complete(ctx, param, "")]
        assert "not:" in items
        assert "gt:" not in items
        assert "contains:" not in items
        assert "since:" not in items

    def test_datetime_column_offers_not_since_before(self, sample_db):
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "created_at")
        items = [c.value for c in param.type.shell_complete(ctx, param, "")]
        assert "not:" in items
        assert "since:" in items
        assert "before:" in items
        assert "gt:" not in items
        assert "contains:" not in items

    def test_prefix_filter_g_matches_gt(self, sample_db):
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "stars")
        items = [c.value for c in param.type.shell_complete(ctx, param, "g")]
        assert "gt:" in items
        assert "lt:" not in items
        assert "not:" not in items

    def test_prefix_filter_co_matches_contains(self, sample_db):
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "language")
        items = [c.value for c in param.type.shell_complete(ctx, param, "co")]
        assert "contains:" in items
        assert "not:" not in items

    def test_null_literal_offered_at_empty(self, sample_db):
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "language")
        items = [c.value for c in param.type.shell_complete(ctx, param, "")]
        assert "null" in items

    def test_null_literal_offered_on_n_prefix(self, sample_db):
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "language")
        items = [c.value for c in param.type.shell_complete(ctx, param, "n")]
        assert "not:" in items
        assert "null" in items

    def test_null_literal_on_nu_filters_out_not(self, sample_db):
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "language")
        items = [c.value for c in param.type.shell_complete(ctx, param, "nu")]
        assert "null" in items
        assert "not:" not in items  # doesn't start with 'nu'


class TestCompletionIntegrationTier2:
    """End-to-end operator completion via Click's BashComplete harness."""

    def test_numeric_column_operator_completion(self, sample_db):
        from click.shell_completion import BashComplete
        from sqlflag.__main__ import main
        comp = BashComplete(main, {}, "sqlflag", "_SQLFLAG_COMPLETE")
        items = [c.value for c in comp.get_completions(
            args=[sample_db, "repos", "--stars"], incomplete=""
        )]
        assert "gt:" in items
        assert "lt:" in items
        assert "not:" in items

    def test_text_column_operator_completion(self, sample_db):
        from click.shell_completion import BashComplete
        from sqlflag.__main__ import main
        comp = BashComplete(main, {}, "sqlflag", "_SQLFLAG_COMPLETE")
        items = [c.value for c in comp.get_completions(
            args=[sample_db, "repos", "--language"], incomplete=""
        )]
        assert "contains:" in items
        assert "not:" in items

    def test_operator_prefix_filter(self, sample_db):
        from click.shell_completion import BashComplete
        from sqlflag.__main__ import main
        comp = BashComplete(main, {}, "sqlflag", "_SQLFLAG_COMPLETE")
        items = [c.value for c in comp.get_completions(
            args=[sample_db, "repos", "--stars"], incomplete="g"
        )]
        assert "gt:" in items
        assert "lt:" not in items


class TestCompletionTier3:
    """Opt-in data-aware value completion, gated by SQLFLAG_COMPLETE_VALUES env var."""

    def _param(self, app, table, col_flag):
        import click
        cmd = app.click_app.commands[table]
        param = next(p for p in cmd.params if p.name == col_flag)
        ctx = click.Context(cmd)
        return ctx, param

    def test_values_off_by_default(self, sample_db, monkeypatch):
        """With no env var, only operators are offered, not data values."""
        monkeypatch.delenv("SQLFLAG_COMPLETE_VALUES", raising=False)
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "language")
        items = [c.value for c in param.type.shell_complete(ctx, param, "")]
        assert "contains:" in items
        assert "not:" in items
        # Data values NOT offered
        assert "python" not in items
        assert "go" not in items

    def test_values_on_with_env_offers_distinct_values(self, sample_db, monkeypatch):
        """With SQLFLAG_COMPLETE_VALUES=1, distinct values are offered alongside operators."""
        monkeypatch.setenv("SQLFLAG_COMPLETE_VALUES", "1")
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "language")
        items = [c.value for c in param.type.shell_complete(ctx, param, "")]
        assert "contains:" in items
        assert "not:" in items
        assert "python" in items
        assert "go" in items
        assert "rust" in items

    def test_values_prefix_filter(self, sample_db, monkeypatch):
        """Prefix matching applies to data values."""
        monkeypatch.setenv("SQLFLAG_COMPLETE_VALUES", "1")
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "language")
        items = [c.value for c in param.type.shell_complete(ctx, param, "py")]
        assert "python" in items
        assert "go" not in items

    def test_cardinality_gate_skips_high_cardinality(self, sample_db, monkeypatch):
        """Columns with cardinality above SQLFLAG_VALUE_COMPLETE_MAX skip value completion."""
        monkeypatch.setenv("SQLFLAG_COMPLETE_VALUES", "1")
        monkeypatch.setenv("SQLFLAG_VALUE_COMPLETE_MAX", "2")
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        # sample_db repos has 4 distinct names (alpha/beta/gamma/delta) > 2
        ctx, param = self._param(app, "repos", "name")
        items = [c.value for c in param.type.shell_complete(ctx, param, "")]
        # Operators still offered
        assert "contains:" in items
        # But no data values (exceeded threshold)
        assert "alpha" not in items
        assert "beta" not in items

    def test_cardinality_at_threshold_still_offers_values(self, sample_db, monkeypatch):
        """Cardinality equal to threshold (not exceeding) still offers values."""
        monkeypatch.setenv("SQLFLAG_COMPLETE_VALUES", "1")
        monkeypatch.setenv("SQLFLAG_VALUE_COMPLETE_MAX", "3")
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        # language has 3 distinct values (python/go/rust) == threshold 3
        ctx, param = self._param(app, "repos", "language")
        items = [c.value for c in param.type.shell_complete(ctx, param, "")]
        assert "python" in items
        assert "go" in items
        assert "rust" in items

    def test_skip_values_when_typing_operator_prefix(self, sample_db, monkeypatch):
        """Once user has typed `gt:`, don't pollute completion with distinct values."""
        monkeypatch.setenv("SQLFLAG_COMPLETE_VALUES", "1")
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "language")
        items = [c.value for c in param.type.shell_complete(ctx, param, "contains:")]
        # Still offers the operator (it matches its own prefix) but no raw values
        assert "python" not in items
        assert "go" not in items

    def test_completion_degrades_silently_on_engine_error(self, sample_db, monkeypatch):
        """Completion must never raise even if data access fails."""
        monkeypatch.setenv("SQLFLAG_COMPLETE_VALUES", "1")
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "language")
        # Sabotage the engine reference on the ParamType so distinct queries raise
        param.type._engine = None
        items = param.type.shell_complete(ctx, param, "")
        # Must not raise; operators still work
        values = [c.value for c in items]
        assert "contains:" in values
        assert "not:" in values

    def test_null_literal_still_offered(self, sample_db, monkeypatch):
        """null remains a completion candidate independent of value completion."""
        monkeypatch.setenv("SQLFLAG_COMPLETE_VALUES", "1")
        from sqlflag.cli import SqlFlag
        app = SqlFlag(sample_db)
        ctx, param = self._param(app, "repos", "language")
        items = [c.value for c in param.type.shell_complete(ctx, param, "nu")]
        assert "null" in items


class TestCompletionIntegrationTier3:
    """End-to-end Tier 3 via BashComplete with env var."""

    def test_values_offered_via_bashcomplete(self, sample_db, monkeypatch):
        monkeypatch.setenv("SQLFLAG_COMPLETE_VALUES", "1")
        from click.shell_completion import BashComplete
        from sqlflag.__main__ import main
        comp = BashComplete(main, {}, "sqlflag", "_SQLFLAG_COMPLETE")
        items = [c.value for c in comp.get_completions(
            args=[sample_db, "repos", "--language"], incomplete=""
        )]
        assert "python" in items
        assert "go" in items
        assert "contains:" in items  # operators still offered

    def test_values_suppressed_without_env(self, sample_db, monkeypatch):
        monkeypatch.delenv("SQLFLAG_COMPLETE_VALUES", raising=False)
        from click.shell_completion import BashComplete
        from sqlflag.__main__ import main
        comp = BashComplete(main, {}, "sqlflag", "_SQLFLAG_COMPLETE")
        items = [c.value for c in comp.get_completions(
            args=[sample_db, "repos", "--language"], incomplete=""
        )]
        assert "python" not in items
        assert "contains:" in items


class TestInstallCompletion:
    """The `--install-completion <shell>` helper that emits shell-completion source."""

    def test_bash(self):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, ["--install-completion", "bash"])
        assert result.exit_code == 0, result.output
        # Click's bash source defines a completion function with this naming pattern
        assert "_sqlflag_completion" in result.output
        assert "complete -o" in result.output or "compopt" in result.output

    def test_zsh(self):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, ["--install-completion", "zsh"])
        assert result.exit_code == 0, result.output
        assert "_sqlflag_completion" in result.output
        # Zsh completion uses compdef
        assert "compdef" in result.output

    def test_fish(self):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, ["--install-completion", "fish"])
        assert result.exit_code == 0, result.output
        # Fish completion uses `complete -c`
        assert "complete" in result.output

    def test_invalid_shell_rejected(self):
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, ["--install-completion", "tcsh"])
        # Click rejects invalid Choice with non-zero exit
        assert result.exit_code != 0

    def test_does_not_require_db_path(self):
        """Install-completion is meta; a db is not needed."""
        from sqlflag.__main__ import main
        runner = CliRunner()
        result = runner.invoke(main, ["--install-completion", "bash"])
        # No db path provided, must still succeed
        assert result.exit_code == 0
        assert len(result.output) > 0
