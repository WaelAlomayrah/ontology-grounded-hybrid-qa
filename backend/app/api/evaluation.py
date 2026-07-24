from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_retriever
from app.evaluation.runner import RESULTS_DIR, run_evaluation
from app.retrieval.hybrid_retriever import HybridRetriever

router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])


@router.post("/run")
async def run(retriever: HybridRetriever = Depends(get_retriever)) -> dict:
    async def ask(question: str, mode: str) -> dict:
        result = await retriever.retrieve(question, mode)
        return {**result.model_dump(), "answer": " ".join(f"{f.subject_label} {f.predicate_label} {f.object_label}." for f in result.retrieval.graph_facts), "answer_status": "answered" if result.retrieval.graph_facts or result.retrieval.vector_results else "insufficient_evidence"}
    return await run_evaluation(Path("/app/data/sample/evaluation_questions.json"), ask)


@router.get("/results")
async def results() -> dict:
    path = RESULTS_DIR / "latest.json"
    if not path.exists(): raise HTTPException(404, detail={"code": "NO_EVALUATION", "message": "No evaluation has run", "details": {}})
    import json
    return json.loads(path.read_text(encoding="utf-8"))

