import json
from io import StringIO
from sqlflag.formatter import format_rows


SAMPLE_ROWS = [
    {"name": "alpha", "stars": 100},
    {"name": "beta", "stars": 50},
]


class TestJsonFormat:
    def test_json_output(self):
        buf = StringIO()
        format_rows(SAMPLE_ROWS, fmt="json", file=buf)
        lines = buf.getvalue().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"name": "alpha", "stars": 100}
        assert json.loads(lines[1]) == {"name": "beta", "stars": 50}


class TestCsvFormat:
    def test_csv_output(self):
        buf = StringIO()
        format_rows(SAMPLE_ROWS, fmt="csv", file=buf)
        lines = buf.getvalue().strip().split("\n")
        assert lines[0] == "name,stars"
        assert lines[1] == "alpha,100"

    def test_csv_empty(self):
        buf = StringIO()
        format_rows([], fmt="csv", file=buf)
        assert buf.getvalue().strip() == ""


class TestTableFormat:
    def test_table_output(self):
        buf = StringIO()
        format_rows(SAMPLE_ROWS, fmt="table", file=buf)
        output = buf.getvalue()
        assert "alpha" in output
        assert "beta" in output
        assert "100" in output


class TestEmpty:
    def test_empty_rows(self):
        buf = StringIO()
        format_rows([], fmt="json", file=buf)
        assert buf.getvalue().strip() == ""
