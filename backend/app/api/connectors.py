import csv
import hashlib
import io
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.auth import require_role
from app.services.workspace_state import save_mapping_profile

router = APIRouter(prefix="/api/v1/connectors", tags=["connectors"])
CONNECTOR_ROOT = Path("/app/data/runtime/connectors")
MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 100_000
MAX_COLUMNS = 200
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _inspect_csv(content: bytes) -> tuple[list[str], list[dict[str, str]], int, str]:
    if b"\x00" in content:
        raise HTTPException(422, detail="CSV contains unsupported null bytes")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(422, detail="CSV must use UTF-8 encoding") from exc
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    columns = [str(column).strip() for column in (reader.fieldnames or [])]
    if len(columns) < 2 or any(not column for column in columns):
        raise HTTPException(422, detail="CSV requires at least two named columns")
    if len(columns) > MAX_COLUMNS or len(set(columns)) != len(columns):
        raise HTTPException(422, detail="CSV headers must be unique and contain at most 200 columns")
    preview: list[dict[str, str]] = []
    row_count = 0
    for row in reader:
        row_count += 1
        if row_count > MAX_ROWS:
            raise HTTPException(413, detail="CSV exceeds the 100,000 row connector limit")
        if len(preview) < 8:
            preview.append({column: str(row.get(column, ""))[:300] for column in columns})
    if row_count == 0:
        raise HTTPException(422, detail="CSV must contain at least one data row")
    return columns, preview, row_count, getattr(dialect, "delimiter", ",")


def _mapping(dataset: str, filename: str, columns: list[str]) -> dict[str, object]:
    lowered = {column.lower(): column for column in columns}
    source_keys, target_keys = {"from", "source", "source_id"}, {"to", "target", "target_id"}
    relationship = bool(source_keys & lowered.keys() and target_keys & lowered.keys())
    identifier_candidates = {"id", "identifier", "entity_id", "uri"}
    label_candidates = {"label", "name", "title"}
    identifier = next((column for column in columns if column.lower() in identifier_candidates or column.lower().endswith("_id")), columns[0])
    label = next((column for column in columns if column.lower() in label_candidates or column.lower().endswith("_name")), columns[min(1, len(columns) - 1)])
    mapped_columns = []
    for column in columns:
        key, role = column.lower(), "attribute"
        if relationship and key in source_keys:
            role = "source"
        elif relationship and key in target_keys:
            role = "target"
        elif relationship and key in {"relation", "predicate", "relationship", "type"}:
            role = "predicate"
        elif not relationship and column == identifier:
            role = "identifier"
        elif not relationship and column == label:
            role = "label"
        mapped_columns.append({"source": column, "target": SAFE_NAME.sub("_", column).strip("_") or "value", "role": role})
    target = "Relationship" if relationship else SAFE_NAME.sub("_", Path(filename).stem).strip("_").title().replace("_", "") or "Entity"
    return {"dataset": dataset, "source": filename, "target_class": target, "mapping_kind": "relationship" if relationship else "entity", "columns": mapped_columns}


def _metadata(path: Path) -> dict[str, object]:
    return json.loads((path / "metadata.json").read_text(encoding="utf-8"))


@router.get("/csv")
async def list_csv_connectors() -> list[dict[str, object]]:
    if not CONNECTOR_ROOT.exists():
        return []
    return sorted((_metadata(path) for path in CONNECTOR_ROOT.iterdir() if path.is_dir() and (path / "metadata.json").exists()), key=lambda item: str(item["created_at"]), reverse=True)


@router.get("/csv/{connector_id}")
async def csv_connector(connector_id: str) -> dict[str, object]:
    path = CONNECTOR_ROOT / connector_id
    if not re.fullmatch(r"[0-9a-f-]{36}", connector_id) or not path.is_dir():
        raise HTTPException(404, detail="CSV connector not found")
    metadata = _metadata(path)
    content = (path / str(metadata["stored_filename"])).read_bytes()
    _, preview, _, _ = _inspect_csv(content)
    return {**metadata, "preview": preview}


@router.post("/csv", dependencies=[Depends(require_role("analyst"))])
async def upload_csv(file: UploadFile = File(...)) -> dict[str, object]:
    original = Path(file.filename or "data.csv").name
    if Path(original).suffix.lower() != ".csv":
        raise HTTPException(415, detail="Only .csv files are supported")
    content = await file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(413, detail="CSV exceeds the 10 MB connector limit")
    columns, preview, row_count, delimiter = _inspect_csv(content)
    digest = hashlib.sha256(content).hexdigest()
    connector_id = str(uuid5(NAMESPACE_URL, f"csv:{digest}"))
    dataset = f"csv:{connector_id}"
    safe_filename = SAFE_NAME.sub("_", original).strip("._") or "data.csv"
    if not safe_filename.lower().endswith(".csv"):
        safe_filename += ".csv"
    path = CONNECTOR_ROOT / connector_id
    path.mkdir(parents=True, exist_ok=True)
    (path / safe_filename).write_bytes(content)
    mapping = _mapping(dataset, safe_filename, columns)
    metadata = {
        "id": connector_id,
        "dataset": dataset,
        "name": Path(original).stem,
        "filename": original,
        "stored_filename": safe_filename,
        "size_bytes": len(content),
        "row_count": row_count,
        "column_count": len(columns),
        "columns": columns,
        "delimiter": delimiter,
        "sha256": digest,
        "created_at": datetime.now(UTC).isoformat(),
        "status": "ready",
    }
    (path / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    save_mapping_profile(dataset, [mapping])
    return {**metadata, "preview": preview, "mapping": mapping}
