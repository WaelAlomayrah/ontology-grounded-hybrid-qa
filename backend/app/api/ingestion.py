import asyncio
import csv
import io
from pathlib import Path
from zipfile import ZipFile
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import require_role
from app.dependencies import get_milvus, require_admin
from app.ingestion import loader
from app.models.api import IngestionJobRequest, IngestionReport, IngestionRequest, MappingProfileRequest
from app.services.milvus_service import MilvusService
from app.services.workspace_state import active_dataset, mapping_profile, mapping_profiles, save_mapping_profile, set_active_dataset, workspace

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])
jobs: dict[str, dict[str, object]] = {}


@router.get("/datasets")
async def datasets() -> list[dict[str, object]]:
    data_root = Path("/app/data")
    catalog: list[dict[str, object]] = []
    for directory in sorted((item for item in data_root.iterdir() if item.is_dir()), key=lambda item: item.name.lower()):
        files = [item for item in directory.rglob("*") if item.is_file()]
        archive_entries: list[str] = []
        for archive in (item for item in files if item.suffix.lower() == ".zip"):
            try:
                with ZipFile(archive) as zipped:
                    archive_entries.extend(name for name in zipped.namelist() if not name.endswith("/"))
            except Exception:
                continue
        data_files = [item for item in files if item.suffix.lower() in {".csv", ".ttl", ".owl", ".rdf", ".json"}]
        catalog.append({
            "id": directory.name,
            "name": directory.name.replace("_", " "),
            "files": len(files),
            "data_files": len(data_files) + len(archive_entries),
            "archives": sum(item.suffix.lower() == ".zip" for item in files),
            "archive_preview": archive_entries[:20],
            "supported_for_ingestion": directory.name in {"sample", "KG2QA_ontology_dataset", "Northwind_dataset"},
        })
    return catalog


@router.get("/mappings")
async def mappings() -> list[dict[str, object]]:
    data_root = Path("/app/data")
    rows: list[dict[str, object]] = []
    for directory in sorted((item for item in data_root.iterdir() if item.is_dir()), key=lambda item: item.name.lower()):
        sources: list[tuple[str, list[str]]] = []
        for path in directory.rglob("*.csv"):
            try:
                with path.open(encoding="utf-8-sig", newline="") as handle:
                    sources.append((path.name, next(csv.reader(handle), [])))
            except (OSError, UnicodeError):
                continue
        for archive in directory.rglob("*.zip"):
            try:
                with ZipFile(archive) as zipped:
                    for name in zipped.namelist():
                        if not name.lower().endswith(".csv"):
                            continue
                        with zipped.open(name) as raw:
                            header = next(csv.reader(io.TextIOWrapper(raw, encoding="utf-8-sig")), [])
                            sources.append((name, header))
            except Exception:
                continue
        for source, columns in sources:
            normalized = {column.lower(): column for column in columns}
            has_edges = any(key in normalized for key in {"from", "source", "source_id", "employee_id"}) and any(key in normalized for key in {"to", "target", "target_id", "project_id"})
            stem = Path(source).stem.replace("-", "_").replace(" ", "_")
            target = "Relationship" if has_edges else "Entity"
            if directory.name == "Northwind_dataset":
                target = {"products": "Product", "customers": "Customer", "suppliers": "Supplier", "employees": "Employee", "orders": "Order", "categories": "Category", "shippers": "Shipper", "regions": "Region", "territories": "Territory"}.get(stem.lower(), "Relationship")
            column_rows = []
            for column in columns:
                key = column.lower()
                role = "attribute"
                if key in {"id", "entity_id", "uri", "identifier"} or key.endswith("id") and not has_edges:
                    role = "identifier"
                elif key in {"label", "name", "title"} or key.endswith("name"):
                    role = "label"
                elif has_edges and key in {"from", "source", "source_id", "employee_id"}:
                    role = "source"
                elif has_edges and key in {"to", "target", "target_id", "project_id"}:
                    role = "target"
                elif key in {"relation", "predicate", "relationship", "type"}:
                    role = "predicate"
                column_rows.append({"source": column, "target": column.replace(" ", "_"), "role": role})
            rows.append({"dataset": directory.name, "source": source, "target_class": target, "mapping_kind": "relationship" if has_edges or target == "Relationship" else "entity", "columns": column_rows})
    for dataset in {str(row["dataset"]) for row in rows}:
        saved = mapping_profile(dataset)
        if saved is not None:
            rows = [row for row in rows if row["dataset"] != dataset] + saved
    known = {str(row["dataset"]) for row in rows}
    for dataset, saved in mapping_profiles().items():
        if dataset not in known:
            rows.extend(saved)
    return rows


@router.put("/mappings", dependencies=[Depends(require_role("analyst"))])
async def update_mappings(request: MappingProfileRequest) -> dict[str, object]:
    errors: list[str] = []
    for mapping in request.mappings:
        roles = {column.role for column in mapping.columns}
        if not mapping.target_class.strip():
            errors.append(f"{mapping.source}: name what one row represents.")
        required = (
            {"identifier": "Unique ID", "label": "Display name"}
            if mapping.mapping_kind == "entity"
            else {"source": "From item", "target": "To item"}
        )
        for role, friendly_name in required.items():
            if role not in roles:
                errors.append(f"{mapping.source}: choose one column as “{friendly_name}”.")
    if not errors: save_mapping_profile(request.dataset, [mapping.model_dump() for mapping in request.mappings])
    return {"valid": not errors, "errors": errors, "saved": not errors}


@router.get("/active")
async def get_active() -> dict[str, str]: return {"dataset": active_dataset()}


@router.put("/active", dependencies=[Depends(require_role("analyst"))])
async def put_active(value: dict[str, str]) -> dict[str, str]:
    dataset = value.get("dataset", "").lower()
    if dataset not in {"sample", "kg2qa", "northwind"}:
        raise HTTPException(status_code=422, detail="Unsupported dataset")
    set_active_dataset(dataset); return {"dataset": dataset}


async def _run_job(job_id: str, request: IngestionJobRequest) -> None:
    jobs[job_id].update({"status": "running", "phase": "discovering", "progress": 5})
    def update(phase: str, percent: int) -> None: jobs[job_id].update({"phase": phase, "progress": percent})
    try:
        report = await loader.ingest(request.dataset, request.mode == "reset", request.load_graph, request.load_vectors, progress=update)
        jobs[job_id].update({"status": "failed" if report.errors else "complete", "progress": 100, "report": report.model_dump()})
        if not report.errors:
            set_active_dataset(request.dataset)
    except Exception as exc:
        jobs[job_id].update({"status": "failed", "phase": "failed", "error": str(exc)[:300]})


@router.post("/jobs", dependencies=[Depends(require_role("admin"))])
async def start_job(request: IngestionJobRequest) -> dict[str, object]:
    job_id = str(uuid4()); jobs[job_id] = {"id": job_id, "dataset": request.dataset, "status": "queued", "phase": "queued", "progress": 0}
    asyncio.create_task(_run_job(job_id, request)); return jobs[job_id]


@router.get("/jobs/{job_id}")
async def job(job_id: str) -> dict[str, object]: return jobs.get(job_id, {"id": job_id, "status": "not_found", "progress": 0})


@router.get("/status")
async def status(milvus: MilvusService = Depends(get_milvus)) -> dict[str, object]:
    try: count = await asyncio.to_thread(milvus.count)
    except Exception: count = None
    return {"latest_report": loader.latest_report.model_dump() if loader.latest_report else None, "vector_count": count, "workspace": workspace(), "active_jobs": list(jobs.values())[-5:]}


@router.post("/sample", response_model=IngestionReport)
async def sample(request: IngestionRequest, _: dict[str, str] = Depends(require_role("admin"))) -> IngestionReport: return await loader.ingest("sample", request.mode == "reset", request.load_graph, request.load_vectors)


@router.post("/kg2qa", response_model=IngestionReport)
async def kg2qa(request: IngestionRequest, _: dict[str, str] = Depends(require_role("admin"))) -> IngestionReport: return await loader.ingest("kg2qa", request.mode == "reset", request.load_graph, request.load_vectors)


@router.post("/northwind", response_model=IngestionReport)
async def northwind(request: IngestionRequest, _: dict[str, str] = Depends(require_role("admin"))) -> IngestionReport: return await loader.ingest("northwind", request.mode == "reset", request.load_graph, request.load_vectors)


@router.post("/reset", dependencies=[Depends(require_admin)])
async def reset() -> IngestionReport: return await loader.ingest("sample", True, True, True)
