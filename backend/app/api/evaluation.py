import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.embedding_models import MODELS, settings_for_index
from app.evaluation.runner import RESULTS_DIR, run_evaluation
from app.models.api import EvaluationRunRequest
from app.retrieval.hybrid_retriever import HybridRetriever
from app.services.embedding_service import EmbeddingService
from app.services.fuseki_service import FusekiService
from app.services.milvus_service import MilvusService
from app.services.workspace_state import active_dataset, workspace

router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])
jobs: dict[str, dict[str, object]] = {}


QUESTION_PATHS = {
    "sample": Path("/app/data/sample/evaluation_questions.json"),
    "kg2qa": Path("/app/data/KG2QA_ontology_dataset/evaluation_questions.json"),
    "arabic_enterprise": Path("/app/data/Arabic_enterprise_dataset/evaluation_questions_ar.json"),
}


@router.get("/options")
async def options() -> dict[str, object]:
    settings = get_settings()
    indexed: list[dict[str, object]] = []
    for dataset in QUESTION_PATHS:
        for model_id, spec in MODELS.items():
            index_settings = settings_for_index(settings, dataset, model_id)
            milvus = MilvusService(index_settings)
            try:
                if milvus.client.has_collection(index_settings.milvus_collection):
                    indexed.append(
                        {
                            "dataset": dataset,
                            "embedding_model": model_id,
                            "model_label": spec.label,
                            "vectors": milvus.count(),
                        }
                    )
            except Exception:
                continue
    return {
        "datasets": list(QUESTION_PATHS),
        "models": [{"id": item.id, "label": item.label} for item in MODELS.values()],
        "indexed": indexed,
        "active": workspace(),
    }


async def _execute_evaluation(
    request: EvaluationRunRequest,
    progress: Callable[[str, int, int], None] | None = None,
) -> dict:
    if request.dataset != active_dataset():
        raise HTTPException(
            409, detail=f"Publish {request.dataset} as the active graph before evaluating it"
        )
    settings = settings_for_index(get_settings(), request.dataset, request.embedding_model)
    milvus = MilvusService(settings)
    if not milvus.client.has_collection(settings.milvus_collection):
        raise HTTPException(
            422,
            detail=f"No {request.embedding_model} vector index exists for {request.dataset}. Ingest it first.",
        )
    retriever = HybridRetriever(
        settings, FusekiService(settings), milvus, EmbeddingService(settings)
    )

    async def ask(question: str, mode: str) -> dict:
        result = await retriever.retrieve(question, mode)
        vector_evidence = " ".join(
            f"{item.label}. {item.text}" for item in result.retrieval.vector_results
        )
        graph_evidence = " ".join(
            f"{fact.subject_label} {fact.predicate_label} {fact.object_label}."
            for fact in result.retrieval.graph_facts
        )
        return {
            **result.model_dump(),
            "answer": " ".join(part for part in (graph_evidence, vector_evidence) if part),
            "answer_status": "answered"
            if result.retrieval.graph_facts or result.retrieval.vector_results
            else "insufficient_evidence",
        }

    questions_path = QUESTION_PATHS.get(request.dataset)
    if questions_path is None or not questions_path.is_file():
        raise HTTPException(
            422, detail=f"No evaluation question set is configured for {request.dataset}"
        )
    # Load the embedding model and execute one unmeasured query before the
    # benchmark so model initialization is not attributed to the first item.
    await retriever.retrieve("evaluation warmup", "vector_only")
    result = await run_evaluation(
        questions_path,
        ask,
        f"{request.dataset}--{request.embedding_model}",
        progress=progress,
    )
    result["dataset"] = request.dataset
    result["embedding_model"] = request.embedding_model
    path = RESULTS_DIR / f"{request.dataset}--{request.embedding_model}.json"
    serialized = __import__("json").dumps(result, indent=2)
    path.write_text(serialized, encoding="utf-8")
    (RESULTS_DIR / "latest.json").write_text(serialized, encoding="utf-8")
    return result


@router.post("/run")
async def run(request: EvaluationRunRequest) -> dict:
    """Synchronous compatibility endpoint; the web client uses background jobs."""
    return await _execute_evaluation(request)


async def _run_job(job_id: str, request: EvaluationRunRequest) -> None:
    jobs[job_id].update(
        {
            "status": "running",
            "phase": "warming_up",
            "progress": 1,
            "started_at": datetime.now(UTC).isoformat(),
        }
    )
    modes = ("vector_only", "graph_only", "hybrid")

    def update(mode: str, current: int, total: int) -> None:
        mode_index = modes.index(mode)
        completed = mode_index * total + current
        jobs[job_id].update(
            {
                "phase": mode,
                "progress": min(99, round(100 * completed / (len(modes) * total))),
                "completed_questions": completed,
                "total_retrievals": len(modes) * total,
            }
        )

    try:
        result = await _execute_evaluation(request, progress=update)
        jobs[job_id].update(
            {
                "status": "complete",
                "phase": "complete",
                "progress": 100,
                "completed_at": datetime.now(UTC).isoformat(),
                "summary": {
                    "question_count": result["question_count"],
                    "ontology_gain": result["ontology_ablation"]["absolute_gain"],
                    "graph_activation_rate": result["ontology"]["graph_activation_rate"],
                },
            }
        )
    except Exception as exc:
        jobs[job_id].update(
            {
                "status": "failed",
                "phase": "failed",
                "progress": 100,
                "completed_at": datetime.now(UTC).isoformat(),
                "error": str(exc)[:500] or type(exc).__name__,
            }
        )


@router.post("/jobs")
async def start_job(request: EvaluationRunRequest) -> dict[str, object]:
    active = next(
        (
            item
            for item in reversed(list(jobs.values()))
            if item.get("status") in {"queued", "running"}
        ),
        None,
    )
    if active is not None:
        raise HTTPException(
            409,
            detail=f"Evaluation job {active['id']} is already running",
        )
    # Validate state before returning a job ID so configuration errors appear
    # immediately instead of becoming opaque background failures.
    if request.dataset != active_dataset():
        raise HTTPException(
            409, detail=f"Publish {request.dataset} as the active graph before evaluating it"
        )
    settings = settings_for_index(get_settings(), request.dataset, request.embedding_model)
    if not MilvusService(settings).client.has_collection(settings.milvus_collection):
        raise HTTPException(
            422,
            detail=f"No {request.embedding_model} vector index exists for {request.dataset}. Ingest it first.",
        )
    job_id = str(uuid4())
    jobs[job_id] = {
        "id": job_id,
        "dataset": request.dataset,
        "embedding_model": request.embedding_model,
        "status": "queued",
        "phase": "queued",
        "progress": 0,
        "created_at": datetime.now(UTC).isoformat(),
    }
    asyncio.create_task(_run_job(job_id, request))
    return jobs[job_id]


@router.get("/jobs/{job_id}")
async def job_status(job_id: str) -> dict[str, object]:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, detail="Evaluation job not found")
    return job


@router.get("/results")
async def results(
    dataset: str | None = Query(default=None),
    embedding_model: str | None = Query(default=None),
) -> dict:
    path = RESULTS_DIR / (
        f"{dataset}--{embedding_model}.json" if dataset and embedding_model else "latest.json"
    )
    if not path.exists():
        raise HTTPException(
            404, detail={"code": "NO_EVALUATION", "message": "No evaluation has run", "details": {}}
        )
    import json

    return json.loads(path.read_text(encoding="utf-8"))
