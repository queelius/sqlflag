import json
from io import StringIO
from sqlflag.formatter import format_rows
from sqlflag.formats import available_formats, get_writer


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


class TestFormatDiscovery:
    def test_builtin_formats_discovered(self):
        fmts = available_formats()
        assert "json" in fmts
        assert "csv" in fmts
        assert "table" in fmts
        assert "arkiv" in fmts

    def test_get_writer_returns_callable(self):
        for name in available_formats():
            assert callable(get_writer(name))

    def test_get_writer_unknown_returns_none(self):
        assert get_writer("nonexistent") is None

    def test_unknown_format_falls_back_to_json(self):
        buf = StringIO()
        format_rows(SAMPLE_ROWS, fmt="nonexistent", file=buf)
        lines = buf.getvalue().strip().split("\n")
        assert json.loads(lines[0]) == {"name": "alpha", "stars": 100}


class TestArkivFormat:
    def test_non_arkiv_columns_go_to_metadata(self):
        buf = StringIO()
        format_rows(SAMPLE_ROWS, fmt="arkiv", file=buf)
        lines = buf.getvalue().strip().split("\n")
        record = json.loads(lines[0])
        assert record["metadata"] == {"name": "alpha", "stars": 100}
        assert "name" not in record
        assert "stars" not in record

    def test_arkiv_known_fields_promoted(self):
        rows = [{"content": "hello", "timestamp": "2025-01-01", "tag": "test"}]
        buf = StringIO()
        format_rows(rows, fmt="arkiv", file=buf)
        record = json.loads(buf.getvalue().strip())
        assert record["content"] == "hello"
        assert record["timestamp"] == "2025-01-01"
        assert record["metadata"] == {"tag": "test"}

    def test_arkiv_all_known_fields(self):
        rows = [{"mimetype": "text/plain", "uri": "http://x", "content": "hi",
                 "timestamp": "2025-01-01", "metadata": {"existing": True}}]
        buf = StringIO()
        format_rows(rows, fmt="arkiv", file=buf)
        record = json.loads(buf.getvalue().strip())
        assert record["mimetype"] == "text/plain"
        assert record["uri"] == "http://x"
        assert record["content"] == "hi"
        assert record["timestamp"] == "2025-01-01"
        assert record["metadata"] == {"existing": True}

    def test_arkiv_metadata_merged_with_extra_columns(self):
        rows = [{"metadata": {"existing": True}, "content": "hi", "extra_col": "oops"}]
        buf = StringIO()
        format_rows(rows, fmt="arkiv", file=buf)
        record = json.loads(buf.getvalue().strip())
        assert record["content"] == "hi"
        assert record["metadata"] == {"existing": True, "extra_col": "oops"}

    def test_arkiv_no_metadata_key_when_all_known(self):
        rows = [{"content": "hello"}]
        buf = StringIO()
        format_rows(rows, fmt="arkiv", file=buf)
        record = json.loads(buf.getvalue().strip())
        assert record == {"content": "hello"}
        assert "metadata" not in record
