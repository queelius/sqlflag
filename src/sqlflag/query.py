"""Query engine: compile filters to parameterized SQL and execute."""

import sqlite3
from sqlite_utils import Database
from sqlflag.parser import parse_value, _coerce_value, OPERATORS
from sqlflag.schema import SchemaInfo


class QueryEngine:
    def __init__(self, db_path: str, schema: SchemaInfo | None = None):
        self._db_path = db_path
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        self._db = Database(conn)
        self._schema = schema or SchemaInfo(db_path)

    def query(
        self,
        table: str,
        filters: dict[str, list[str]] | None = None,
        conjunction: str = "all",
        order: list[str] | None = None,
        limit: int | None = None,
        columns: list[str] | None = None,
        search: str | None = None,
    ) -> list[dict]:
        where_clause, params = self._compile_filters(table, filters or {}, conjunction)
        order_clause = self._compile_order(order)
        select = ", ".join(f"[{c}]" for c in columns) if columns else "*"

        # FTS search: AND with other filters via rowid subquery
        if search:
            fts_condition = f"[{table}].rowid IN (SELECT rowid FROM [{table}_fts] WHERE [{table}_fts] MATCH ?)"
            params.insert(0, search)
            if where_clause:
                where_clause = f"{fts_condition} AND ({where_clause})"
            else:
                where_clause = fts_condition

        sql = f"SELECT {select} FROM [{table}]"
        if where_clause:
            sql += f" WHERE {where_clause}"
        if order_clause:
            sql += f" ORDER BY {order_clause}"
        if limit is not None:
            sql += f" LIMIT {limit}"

        return [dict(row) for row in self._db.execute(sql, params).fetchall()]

    def execute_sql(self, sql: str) -> list[dict]:
        return [dict(row) for row in self._db.execute(sql).fetchall()]

    def search(self, table: str, query: str) -> list[dict]:
        return list(self._db[table].search(query))

    def _compile_filters(self, table, filters, conjunction):
        if not filters:
            return "", []

        flag_clauses = []
        all_params = []

        for col_name, values in filters.items():
            col_type = self._schema.type_category(table, col_name)
            bare_values = []
            op_fragments = []
            op_params = []

            for v in values:
                has_op = False
                for op_name in OPERATORS:
                    if v.startswith(op_name + ":"):
                        has_op = True
                        break

                if v == "null" or has_op:
                    frag, params = parse_value(col_name, v, col_type)
                    op_fragments.append(frag)
                    op_params.extend(params)
                else:
                    bare_values.append(v)

            col_conditions = []
            col_params = []
            if len(bare_values) == 1:
                frag, params = parse_value(col_name, bare_values[0], col_type)
                col_conditions.append(frag)
                col_params.extend(params)
            elif len(bare_values) > 1:
                coerced = [_coerce_value(v, col_type) for v in bare_values]
                placeholders = ", ".join("?" for _ in coerced)
                col_conditions.append(f"[{col_name}] IN ({placeholders})")
                col_params.extend(coerced)

            col_conditions.extend(op_fragments)
            col_params.extend(op_params)

            if col_conditions:
                within = " AND ".join(col_conditions)
                if len(col_conditions) > 1:
                    within = f"({within})"
                flag_clauses.append(within)
                all_params.extend(col_params)

        if not flag_clauses:
            return "", []

        joiner = " OR " if conjunction == "any" else " AND "
        where = joiner.join(flag_clauses)
        return where, all_params

    def _compile_order(self, order):
        if not order:
            return ""
        parts = []
        for spec in order:
            if spec.startswith("-"):
                col = spec[1:].replace("-", "_")
                parts.append(f"[{col}] DESC")
            else:
                col = spec.replace("-", "_")
                parts.append(f"[{col}]")
        return ", ".join(parts)
