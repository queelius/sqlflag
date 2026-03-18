"""Schema introspection and type categorization."""

from sqlite_utils import Database

RESERVED_FLAGS = frozenset({
    "all", "any", "order", "limit", "columns", "format", "search", "help",
})

TYPE_CATEGORIES = {
    "TEXT": "TEXT",
    "VARCHAR": "TEXT",
    "CHAR": "TEXT",
    "CLOB": "TEXT",
    "INTEGER": "INTEGER",
    "INT": "INTEGER",
    "BIGINT": "INTEGER",
    "SMALLINT": "INTEGER",
    "TINYINT": "INTEGER",
    "REAL": "REAL",
    "FLOAT": "REAL",
    "DOUBLE": "REAL",
    "NUMERIC": "REAL",
    "BOOLEAN": "BOOLEAN",
    "BOOL": "BOOLEAN",
    "DATETIME": "DATETIME",
    "TIMESTAMP": "DATETIME",
    "DATE": "DATETIME",
}

OPERATORS_BY_TYPE = {
    "TEXT": ["not", "contains"],
    "INTEGER": ["not", "gt", "lt"],
    "REAL": ["not", "gt", "lt"],
    "BOOLEAN": ["not"],
    "DATETIME": ["not", "since", "before"],
}


class SchemaInfo:
    def __init__(self, db_path: str, tables: list[str] | None = None):
        import sqlite3
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        self._db = Database(conn)
        self._tables_allowlist = tables

    def table_names(self) -> list[str]:
        return self._db.table_names()

    def view_names(self) -> list[str]:
        return self._db.view_names()

    def queryable_names(self) -> list[str]:
        all_names = self.table_names() + self.view_names()
        fts_suffixes = ("_fts", "_fts_data", "_fts_idx", "_fts_content", "_fts_docsize", "_fts_config")
        all_names = [n for n in all_names if not any(n.endswith(s) for s in fts_suffixes)]
        if self._tables_allowlist is not None:
            return [n for n in self._tables_allowlist if n in all_names]
        return all_names

    def columns(self, table: str):
        return self._db[table].columns

    def flaggable_columns(self, table: str):
        return [
            c for c in self.columns(table)
            if c.name.lower() not in RESERVED_FLAGS
            and c.name.isidentifier()
            and not c.name.startswith("_")
        ]

    def type_category(self, table: str, column: str) -> str:
        for col in self.columns(table):
            if col.name == column:
                raw = (col.type or "").upper().strip()
                return TYPE_CATEGORIES.get(raw, "TEXT")
        return "TEXT"

    def operators_for(self, table: str, column: str) -> list[str]:
        cat = self.type_category(table, column)
        return OPERATORS_BY_TYPE.get(cat, OPERATORS_BY_TYPE["TEXT"])

    def row_count(self, table: str) -> int:
        return self._db[table].count

    def has_fts(self, table: str) -> bool:
        fts_table = f"{table}_fts"
        return fts_table in self._db.table_names()
