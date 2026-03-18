import json
from click.testing import CliRunner
from sqlflag.cli import SqlFlag


class TestQueryCommands:
    def test_query_all_rows(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, ["query", "repos", "--format", "json"])
        assert result.exit_code == 0, result.output
        lines = result.output.strip().split("\n")
        assert len(lines) == 4

    def test_query_equality_filter(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "query", "repos", "--language", "python", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert len(rows) == 2
        assert all(r["language"] == "python" for r in rows)

    def test_query_operator_filter(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "query", "repos", "--stars", "gt:75", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert all(r["stars"] > 75 for r in rows)

    def test_query_multiple_values_in(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "query", "repos",
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
            "query", "repos", "--order", "-stars", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert rows[0]["stars"] >= rows[-1]["stars"]

    def test_query_limit(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "query", "repos", "--limit", "2", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        lines = result.output.strip().split("\n")
        assert len(lines) == 2

    def test_query_columns(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "query", "repos", "--columns", "name,stars", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        row = json.loads(result.output.strip().split("\n")[0])
        assert set(row.keys()) == {"name", "stars"}

    def test_query_any_mode(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "query", "repos",
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
            "query", "active_repos", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert all(r["is_archived"] == 0 for r in rows)

    def test_query_contains(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "query", "repos", "--name", "contains:lph", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert len(rows) == 1
        assert rows[0]["name"] == "alpha"

    def test_hyphenated_flag(self, sample_db):
        app = SqlFlag(sample_db)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "query", "repos", "--created-at", "since:2025-01-01", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert len(rows) == 2


class TestTableAllowlist:
    def test_only_allowed_tables(self, sample_db):
        app = SqlFlag(sample_db, tables=["repos"])
        runner = CliRunner()
        result = runner.invoke(app.click_app, ["query", "repos", "--format", "json"])
        assert result.exit_code == 0
        result = runner.invoke(app.click_app, ["query", "events", "--format", "json"])
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


class TestMount:
    def test_mount_into_typer(self, sample_db):
        import typer
        main = typer.Typer()

        @main.command()
        def hello():
            print("hello")

        click_app = SqlFlag(sample_db).mount(main)
        runner = CliRunner()

        result = runner.invoke(click_app, ["query", "repos", "--format", "json"])
        assert result.exit_code == 0

        result = runner.invoke(click_app, [
            "sql", "SELECT count(*) as n FROM repos", "--format", "json",
        ])
        assert result.exit_code == 0

        result = runner.invoke(click_app, ["hello"])
        assert result.exit_code == 0

    def test_mount_custom_query_name(self, sample_db):
        import typer
        main = typer.Typer()
        click_app = SqlFlag(sample_db).mount(main, query_name="db")
        runner = CliRunner()
        result = runner.invoke(click_app, ["db", "repos", "--format", "json"])
        assert result.exit_code == 0


class TestSearchCommand:
    def test_fts_search(self, sample_db_with_fts):
        app = SqlFlag(sample_db_with_fts)
        runner = CliRunner()
        result = runner.invoke(app.click_app, [
            "query", "repos", "--search", "alpha", "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        rows = [json.loads(line) for line in result.output.strip().split("\n")]
        assert any(r["name"] == "alpha" for r in rows)
