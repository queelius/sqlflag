"""Parse op:value flag values into SQL fragments with parameters."""

from datetime import datetime, timedelta
import re

OPERATORS = {
    "not": "not",
    "gt": "gt",
    "lt": "lt",
    "contains": "contains",
    "since": "since",
    "before": "before",
}

_RELATIVE_DATE_RE = re.compile(r"^(\d+)(min|h|d|w|mo|y)$")


def parse_relative_date(value: str) -> str | None:
    match = _RELATIVE_DATE_RE.match(value)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    now = datetime.now()
    if unit == "min":
        dt = now - timedelta(minutes=amount)
    elif unit == "h":
        dt = now - timedelta(hours=amount)
    elif unit == "d":
        dt = now - timedelta(days=amount)
    elif unit == "w":
        dt = now - timedelta(weeks=amount)
    elif unit == "mo":
        dt = now - timedelta(days=amount * 30)
    elif unit == "y":
        dt = now - timedelta(days=amount * 365)
    else:
        return None
    return dt.isoformat()


def _coerce_value(value: str, col_type: str) -> int | float | str:
    col_type_upper = (col_type or "").upper()
    if col_type_upper == "INTEGER":
        try:
            return int(value)
        except ValueError:
            return value
    if col_type_upper == "REAL":
        try:
            return float(value)
        except ValueError:
            return value
    return value


def parse_value(column: str, value: str, col_type: str = "TEXT") -> tuple[str, list]:
    # Rule 1: check for known operator prefix
    for op_name in OPERATORS:
        prefix = op_name + ":"
        if value.startswith(prefix):
            rest = value[len(prefix):]
            return _apply_operator(column, op_name, rest, col_type)

    # Rule 2: literal null
    if value == "null":
        return f"{column} IS NULL", []

    # Rule 3: bare value = equality
    coerced = _coerce_value(value, col_type)
    return f"{column} = ?", [coerced]


def _apply_operator(column: str, op: str, value: str, col_type: str) -> tuple[str, list]:
    if op == "not":
        if value == "null":
            return f"{column} IS NOT NULL", []
        coerced = _coerce_value(value, col_type)
        return f"{column} != ?", [coerced]

    if op == "gt":
        coerced = _coerce_value(value, col_type)
        return f"{column} > ?", [coerced]

    if op == "lt":
        coerced = _coerce_value(value, col_type)
        return f"{column} < ?", [coerced]

    if op == "contains":
        escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"{column} LIKE ? ESCAPE '\\'", [f"%{escaped}%"]

    if op == "since":
        resolved = parse_relative_date(value) or value
        return f"{column} >= ?", [resolved]

    if op == "before":
        resolved = parse_relative_date(value) or value
        return f"{column} < ?", [resolved]

    coerced = _coerce_value(value, col_type)
    return f"{column} = ?", [coerced]
