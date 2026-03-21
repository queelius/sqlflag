import pytest
from sqlflag.query import QueryEngine


class TestBasicQueries:
    def test_unfiltered(self, sample_db):
        engine = QueryEngine(sample_db)
        rows = list(engine.query("repos"))
        assert len(rows) == 4

    def test_equality_filter(self, sample_db):
        engine = QueryEngine(sample_db)
        rows = list(engine.query("repos", filters={"language": ["python"]}))
        assert len(rows) == 2
        assert all(r["language"] == "python" for r in rows)

    def test_gt_filter(self, sample_db):
        engine = QueryEngine(sample_db)
        rows = list(engine.query("repos", filters={"stars": ["gt:75"]}))
        assert len(rows) == 2
        assert all(r["stars"] > 75 for r in rows)

    def test_contains_filter(self, sample_db):
        engine = QueryEngine(sample_db)
        rows = list(engine.query("repos", filters={"name": ["contains:lph"]}))
        assert len(rows) == 1
        assert rows[0]["name"] == "alpha"

    def test_not_filter(self, sample_db):
        engine = QueryEngine(sample_db)
        rows = list(engine.query("repos", filters={"language": ["not:python"]}))
        assert len(rows) == 2
        assert all(r["language"] != "python" for r in rows)

    def test_null_filter(self, sample_db):
        engine = QueryEngine(sample_db)
        rows = list(engine.query("repos", filters={"description": ["null"]}))
        assert len(rows) == 1
        assert rows[0]["name"] == "gamma"


class TestMultipleValues:
    def test_in_clause(self, sample_db):
        engine = QueryEngine(sample_db)
        rows = list(engine.query("repos", filters={"language": ["python", "go"]}))
        assert len(rows) == 3

    def test_range(self, sample_db):
        engine = QueryEngine(sample_db)
        rows = list(engine.query("repos", filters={"stars": ["gt:50", "lt:150"]}))
        assert len(rows) == 2
        assert all(50 < r["stars"] < 150 for r in rows)


class TestConjunction:
    def test_and_across_flags(self, sample_db):
        engine = QueryEngine(sample_db)
        rows = list(engine.query("repos", filters={
            "language": ["python"], "stars": ["gt:150"],
        }))
        assert len(rows) == 1
        assert rows[0]["name"] == "gamma"

    def test_or_across_flags(self, sample_db):
        engine = QueryEngine(sample_db)
        rows = list(engine.query("repos", filters={
            "language": ["go"], "stars": ["gt:150"],
        }, conjunction="any"))
        assert len(rows) == 2


class TestOrderAndLimit:
    def test_order_asc(self, sample_db):
        engine = QueryEngine(sample_db)
        rows = list(engine.query("repos", order=["stars"]))
        assert rows[0]["stars"] <= rows[-1]["stars"]

    def test_order_desc(self, sample_db):
        engine = QueryEngine(sample_db)
        rows = list(engine.query("repos", order=["-stars"]))
        assert rows[0]["stars"] >= rows[-1]["stars"]

    def test_limit(self, sample_db):
        engine = QueryEngine(sample_db)
        rows = list(engine.query("repos", limit=2))
        assert len(rows) == 2

    def test_columns_select(self, sample_db):
        engine = QueryEngine(sample_db)
        rows = list(engine.query("repos", columns=["name", "stars"]))
        assert set(rows[0].keys()) == {"name", "stars"}


class TestRawSql:
    def test_raw_sql(self, sample_db):
        engine = QueryEngine(sample_db)
        rows = list(engine.execute_sql("SELECT name FROM repos WHERE stars > 100"))
        assert len(rows) == 1
        assert rows[0]["name"] == "gamma"

    def test_raw_sql_read_only(self, sample_db):
        engine = QueryEngine(sample_db)
        with pytest.raises(Exception):
            list(engine.execute_sql("DROP TABLE repos"))


class TestViews:
    def test_query_view(self, sample_db):
        engine = QueryEngine(sample_db)
        rows = list(engine.query("active_repos"))
        assert len(rows) == 3
        assert all(r["is_archived"] == 0 for r in rows)


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


class TestSearch:
    def test_fts_search(self, sample_db_with_fts):
        engine = QueryEngine(sample_db_with_fts)
        rows = list(engine.search("repos", "alpha"))
        assert len(rows) >= 1
        assert any(r["name"] == "alpha" for r in rows)

    def test_fts_search_with_filter(self, sample_db_with_fts):
        engine = QueryEngine(sample_db_with_fts)
        rows = engine.query("repos", filters={"language": ["python"]}, search="alpha")
        assert len(rows) == 1
        assert rows[0]["name"] == "alpha"
