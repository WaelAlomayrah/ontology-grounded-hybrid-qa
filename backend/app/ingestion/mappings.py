from collections.abc import Iterable

SOURCE_COLUMNS = ("source", "source_id", "subject", "head", "from", "employee_id")
TARGET_COLUMNS = ("target", "target_id", "object", "tail", "to", "project_id")
RELATION_COLUMNS = ("relation", "predicate", "relationship", "type")
ID_COLUMNS = ("id", "entity_id", "uri", "identifier")
LABEL_COLUMNS = ("label", "name", "title")


def detect_column(columns: Iterable[str], candidates: Iterable[str], required: bool = True) -> str | None:
    normalized = {column.strip().lower(): column for column in columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    if required:
        raise ValueError(f"None of columns {tuple(candidates)} found in {tuple(columns)}")
    return None

