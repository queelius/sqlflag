import warnings

import pytest

from sqlflag.schema import SchemaInfo


class TestSchemaInfo:
    def test_table_names(self, sample_db):
        info = SchemaInfo(sample_db)
        names = info.table_names()
        assert "repos" in names
        assert "events" in names

    def test_view_names(self, sample_db):
        info = SchemaInfo(sample_db)
        names = info.view_names()
        assert "active_repos" in names

    def test_all_queryable(self, sample_db):
        info = SchemaInfo(sample_db)
        names = info.queryable_names()
        assert "repos" in names
        assert "events" in names
        assert "active_repos" in names

    def test_columns(self, sample_db):
        info = SchemaInfo(sample_db)
        cols = info.columns("repos")
        col_names = [c.name for c in cols]
        assert "name" in col_names
        assert "stars" in col_names
        assert "created_at" in col_names

    def test_column_type_category(self, sample_db):
        info = SchemaInfo(sample_db)
        assert info.type_category("repos", "name") == "TEXT"
        assert info.type_category("repos", "stars") == "INTEGER"
        assert info.type_category("repos", "is_archived") == "BOOLEAN"
        assert info.type_category("repos", "created_at") == "DATETIME"

    def test_operators_for_column(self, sample_db):
        info = SchemaInfo(sample_db)
        text_ops = info.operators_for("repos", "name")
        assert "not" in text_ops
        assert "contains" in text_ops
        assert "gt" not in text_ops

        int_ops = info.operators_for("repos", "stars")
        assert "gt" in int_ops
        assert "lt" in int_ops
        assert "contains" not in int_ops

        dt_ops = info.operators_for("repos", "created_at")
        assert "since" in dt_ops
        assert "before" in dt_ops
        assert "gt" not in dt_ops

    def test_row_count(self, sample_db):
        info = SchemaInfo(sample_db)
        assert info.row_count("repos") == 4
        assert info.row_count("events") == 3

    def test_has_fts(self, sample_db):
        info = SchemaInfo(sample_db)
        assert info.has_fts("repos") is False

    def test_has_fts_with_index(self, sample_db_with_fts):
        info = SchemaInfo(sample_db_with_fts)
        assert info.has_fts("repos") is True

    def test_tables_allowlist(self, sample_db):
        info = SchemaInfo(sample_db, tables=["repos"])
        assert info.queryable_names() == ["repos"]
        assert "events" in info.table_names()

    def test_reserved_columns_excluded(self, sample_db):
        info = SchemaInfo(sample_db)
        flaggable = info.flaggable_columns("edge_cases")
        col_names = [c.name for c in flaggable]
        assert "format" not in col_names
        assert "name" in col_names
        assert "id" in col_names

    def test_fts_tables_filtered(self, sample_db_with_fts):
        info = SchemaInfo(sample_db_with_fts)
        names = info.queryable_names()
        assert "repos" in names
        assert "repos_fts" not in names

    def test_tables_named_sql_and_schema_allowed(self, sample_db):
        """Tables named 'sql' or 'schema' are allowed now that tables are namespaced."""
        from sqlite_utils import Database
        db = Database(sample_db)
        db.execute("CREATE TABLE [schema] (id INTEGER, data TEXT)")
        db.execute("CREATE TABLE [sql] (id INTEGER, query TEXT)")

        info = SchemaInfo(sample_db)
        names = info.queryable_names()
        assert "schema" in names
        assert "sql" in names

    def test_reserved_columns_emit_warning(self, sample_db):
        """Reserved column names emit warnings when skipped."""
        info = SchemaInfo(sample_db)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            flaggable = info.flaggable_columns("edge_cases")

        col_names = [c.name for c in flaggable]
        assert "format" not in col_names
        assert "name" in col_names
        msgs = [str(x.message) for x in w]
        assert any("format" in m and "conflicts" in m for m in msgs)
