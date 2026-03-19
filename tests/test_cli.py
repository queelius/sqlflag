import json
from click.testing import CliRunner
from sqlflag.cli import SqlFlag


class TestQueryCommands:
    def test_query_all_rows(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, ["table", "repos", "--format", "json"])
        assert result.exit_code == 0, result.output
        lines = result.output.strip().split("\n")
        assert len(lines) == 4

    def test_query_equality_filter(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "table", "repos", "--language", "python", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert len(rows) == 2
        assert all(r["language"] == "python" for r in rows)

    def test_query_operator_filter(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "table", "repos", "--stars", "gt:75", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert all(r["stars"] > 75 for r in rows)

    def test_query_multiple_values_in(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "table", "repos",
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
            "table", "repos", "--order", "-stars", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert rows[0]["stars"] >= rows[-1]["stars"]

    def test_query_limit(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "table", "repos", "--limit", "2", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        lines = result.output.strip().split("\n")
        assert len(lines) == 2

    def test_query_columns(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "table", "repos", "--columns", "name,stars", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        row = json.loads(result.output.strip().split("\n")[0])
        assert set(row.keys()) == {"name", "stars"}

    def test_query_any_mode(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "table", "repos",
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
            "table", "active_repos", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert all(r["is_archived"] == 0 for r in rows)

    def test_query_contains(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "table", "repos", "--name", "contains:lph", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert len(rows) == 1
        assert rows[0]["name"] == "alpha"

    def test_hyphenated_flag(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "table", "repos", "--created-at", "since:2025-01-01", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert len(rows) == 2


class TestTableAllowlist:
    def test_only_allowed_tables(self, sample_db):
        app = SqlFlag(sample_db, tables=["repos"])
        runner = CliRunner()
        result = runner.invoke(app.click_app, ["table", "repos", "--format", "json"])
        assert result.exit_code == 0
        result = runner.invoke(app.click_app, ["table", "events", "--format", "json"])
        assert result.exit_code != 0


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


class TestClickAdapter:
    def test_mount_into_click_group(self, sample_db):
        import click
        from sqlflag.adapters.click_adapter import mount

        main = click.Group()

        @main.command()
        def hello():
            click.echo("hello")

        mount(main, SqlFlag(sample_db))
        runner = CliRunner()

        # Table commands under "query table" path
        result = runner.invoke(main, ["query", "table", "repos", "--format", "json"])
        assert result.exit_code == 0

        # sql and schema under "query" group
        result = runner.invoke(main, ["query", "sql", "SELECT count(*) as n FROM repos", "--format", "json"])
        assert result.exit_code == 0

        result = runner.invoke(main, ["query", "schema", "repos"])
        assert result.exit_code == 0

        # Original commands unaffected
        result = runner.invoke(main, ["hello"])
        assert result.exit_code == 0

    def test_custom_query_name(self, sample_db):
        import click
        from sqlflag.adapters.click_adapter import mount

        main = click.Group()
        mount(main, SqlFlag(sample_db), query_name="browse")
        runner = CliRunner()
        result = runner.invoke(main, ["browse", "table", "repos", "--format", "json"])
        assert result.exit_code == 0
        result = runner.invoke(main, ["browse", "schema"])
        assert result.exit_code == 0


class TestTyperAdapter:
    def test_mount_into_typer(self, sample_db):
        import typer
        from sqlflag.adapters.typer_adapter import mount

        main = typer.Typer()

        @main.command()
        def hello():
            print("hello")

        click_app = mount(main, SqlFlag(sample_db))
        runner = CliRunner()

        result = runner.invoke(click_app, ["query", "table", "repos", "--format", "json"])
        assert result.exit_code == 0

        result = runner.invoke(click_app, ["query", "sql", "SELECT count(*) as n FROM repos", "--format", "json"])
        assert result.exit_code == 0

        result = runner.invoke(click_app, ["hello"])
        assert result.exit_code == 0

    def test_custom_query_name(self, sample_db):
        import typer
        from sqlflag.adapters.typer_adapter import mount

        main = typer.Typer()
        click_app = mount(main, SqlFlag(sample_db), query_name="db")
        runner = CliRunner()
        result = runner.invoke(click_app, ["db", "table", "repos", "--format", "json"])
        assert result.exit_code == 0


class TestArgparseAdapter:
    def test_mount_and_invoke_query(self, sample_db):
        import argparse
        from sqlflag.adapters.argparse_adapter import mount, invoke

        parser = argparse.ArgumentParser()
        mount(parser, SqlFlag(sample_db))

        # Table commands go under: myapp query table repos ...
        args = parser.parse_args(["query", "table", "repos", "--format", "json"])
        assert hasattr(args, "_sqlflag_cmd")

    def test_mount_sql_under_group(self, sample_db):
        import argparse
        from sqlflag.adapters.argparse_adapter import mount

        parser = argparse.ArgumentParser()
        mount(parser, SqlFlag(sample_db))

        # sql is accessed as: myapp query sql "SELECT ..."
        args = parser.parse_args(["query", "sql", "SELECT 1"])
        assert hasattr(args, "_sqlflag_cmd")

    def test_mount_schema_under_group(self, sample_db):
        import argparse
        from sqlflag.adapters.argparse_adapter import mount

        parser = argparse.ArgumentParser()
        mount(parser, SqlFlag(sample_db))

        # schema is accessed as: myapp query schema
        args = parser.parse_args(["query", "schema"])
        assert hasattr(args, "_sqlflag_cmd")

    def test_invoke_returns_false_for_non_sqlflag(self, sample_db):
        import argparse
        from sqlflag.adapters.argparse_adapter import invoke

        ns = argparse.Namespace(command="other")
        assert invoke(ns) is False


class TestConvenienceMount:
    """Test the SqlFlag.mount() convenience method that auto-detects framework."""

    def test_mount_click(self, sample_db):
        import click
        main = click.Group()
        SqlFlag(sample_db).mount(main)
        runner = CliRunner()
        result = runner.invoke(main, ["query", "table", "repos", "--format", "json"])
        assert result.exit_code == 0
        result = runner.invoke(main, ["query", "schema"])
        assert result.exit_code == 0

    def test_mount_typer(self, sample_db):
        import typer
        main = typer.Typer()
        click_app = SqlFlag(sample_db).mount(main)
        runner = CliRunner()
        result = runner.invoke(click_app, ["query", "table", "repos", "--format", "json"])
        assert result.exit_code == 0

    def test_mount_argparse(self, sample_db):
        import argparse
        parser = argparse.ArgumentParser()
        SqlFlag(sample_db).mount(parser)
        args = parser.parse_args(["query", "table", "repos", "--format", "json"])
        assert hasattr(args, "_sqlflag_cmd")


class TestSearchCommand:
    def test_fts_search(self, sample_db_with_fts):
        app = SqlFlag(sample_db_with_fts)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "table", "repos", "--search", "alpha", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert any(r["name"] == "alpha" for r in rows)
