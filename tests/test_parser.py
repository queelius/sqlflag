import pytest
from datetime import datetime, timedelta
from sqlflag.parser import parse_value


class TestBareValues:
    def test_equality_string(self):
        frag, params = parse_value("language", "python")
        assert frag == "language = ?"
        assert params == ["python"]

    def test_equality_integer(self):
        frag, params = parse_value("stars", "50", col_type="INTEGER")
        assert frag == "stars = ?"
        assert params == [50]

    def test_null(self):
        frag, params = parse_value("description", "null")
        assert frag == "description IS NULL"
        assert params == []

    def test_unknown_prefix_treated_as_literal(self):
        frag, params = parse_value("url", "http://example.com")
        assert frag == "url = ?"
        assert params == ["http://example.com"]

    def test_colon_in_value_not_operator(self):
        frag, params = parse_value("tag", "foo:bar")
        assert frag == "tag = ?"
        assert params == ["foo:bar"]


class TestOperators:
    def test_not(self):
        frag, params = parse_value("language", "not:python")
        assert frag == "language != ?"
        assert params == ["python"]

    def test_not_null(self):
        frag, params = parse_value("description", "not:null")
        assert frag == "description IS NOT NULL"
        assert params == []

    def test_gt(self):
        frag, params = parse_value("stars", "gt:50", col_type="INTEGER")
        assert frag == "stars > ?"
        assert params == [50]

    def test_lt(self):
        frag, params = parse_value("stars", "lt:100", col_type="INTEGER")
        assert frag == "stars < ?"
        assert params == [100]

    def test_contains(self):
        frag, params = parse_value("description", "contains:test")
        assert frag == "description LIKE ? ESCAPE '\\'"
        assert params == ["%test%"]


class TestDateOperators:
    def test_since_absolute(self):
        frag, params = parse_value("created_at", "since:2024-01-01")
        assert frag == "created_at >= ?"
        assert params == ["2024-01-01"]

    def test_before_absolute(self):
        frag, params = parse_value("created_at", "before:2025-06-15")
        assert frag == "created_at < ?"
        assert params == ["2025-06-15"]

    def test_since_relative_days(self):
        frag, params = parse_value("created_at", "since:30d")
        assert frag == "created_at >= ?"
        assert len(params) == 1
        parsed = datetime.fromisoformat(params[0])
        delta = datetime.now() - parsed
        assert 29 <= delta.days <= 31

    def test_since_relative_hours(self):
        frag, params = parse_value("timestamp", "since:6h")
        assert frag == "timestamp >= ?"
        parsed = datetime.fromisoformat(params[0])
        delta = datetime.now() - parsed
        assert 5 * 3600 <= delta.total_seconds() <= 7 * 3600

    def test_since_relative_weeks(self):
        frag, params = parse_value("created_at", "since:2w")
        assert frag == "created_at >= ?"
        parsed = datetime.fromisoformat(params[0])
        delta = datetime.now() - parsed
        assert 13 <= delta.days <= 15

    def test_since_relative_months(self):
        frag, params = parse_value("created_at", "since:3mo")
        assert frag == "created_at >= ?"
        parsed = datetime.fromisoformat(params[0])
        delta = datetime.now() - parsed
        assert 80 <= delta.days <= 100

    def test_since_relative_minutes(self):
        frag, params = parse_value("timestamp", "since:30min")
        assert frag == "timestamp >= ?"
        parsed = datetime.fromisoformat(params[0])
        delta = datetime.now() - parsed
        assert 25 * 60 <= delta.total_seconds() <= 35 * 60

    def test_since_relative_years(self):
        frag, params = parse_value("created_at", "since:1y")
        assert frag == "created_at >= ?"
        parsed = datetime.fromisoformat(params[0])
        delta = datetime.now() - parsed
        assert 350 <= delta.days <= 380


class TestTypeCoercion:
    def test_integer_coercion(self):
        _, params = parse_value("stars", "50", col_type="INTEGER")
        assert params == [50]
        assert isinstance(params[0], int)

    def test_real_coercion(self):
        _, params = parse_value("score", "3.14", col_type="REAL")
        assert params == [3.14]
        assert isinstance(params[0], float)

    def test_text_no_coercion(self):
        _, params = parse_value("name", "50", col_type="TEXT")
        assert params == ["50"]
        assert isinstance(params[0], str)

    def test_default_str(self):
        _, params = parse_value("name", "50")
        assert params == ["50"]
