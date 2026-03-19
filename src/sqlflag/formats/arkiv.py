"""arkiv universal record format (JSONL).

Exports query results as arkiv records. Columns matching arkiv's known
top-level fields (mimetype, uri, content, timestamp) are promoted;
everything else goes into ``metadata``.
"""

import json

KNOWN_FIELDS = frozenset({"mimetype", "uri", "content", "timestamp", "metadata"})


def write(rows: list[dict], file) -> None:
    for row in rows:
        record = {}
        metadata = {}
        for key, value in row.items():
            if key in KNOWN_FIELDS:
                record[key] = value
            else:
                metadata[key] = value
        if metadata:
            existing = record.get("metadata")
            if isinstance(existing, dict):
                existing.update(metadata)
            else:
                record["metadata"] = metadata
        file.write(json.dumps(record, default=str) + "\n")
