import time

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.dependencies import get_ollama, get_retriever
from app.metrics import (
    ANSWER_STATUS,
    CHAT_FAILURES,
    CHAT_REQUESTS,
    OLLAMA_LATENCY,
    RETRIEVAL_LATENCY,
    RETRIEVAL_MODES,
)
from app.models.api import ChatResponse, QuestionRequest
from app.models.retrieval import QueryPlan, RetrievalResult
from app.retrieval.context_builder import build_context
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.intent_classifier import classify_intent, extract_entity_mentions
from app.services.language_service import localized_message
from app.services.ollama_service import OllamaService
from app.services.ontology_service import OntologyService

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/retrieve", response_model=RetrievalResult)
async def retrieve(request: QuestionRequest, retriever: HybridRetriever = Depends(get_retriever)) -> RetrievalResult:
    RETRIEVAL_MODES.labels(request.mode).inc()
    with RETRIEVAL_LATENCY.labels(request.mode).time():
        result = await retriever.retrieve(request.question, request.mode)
    if not result.retrieval.graph_facts and not result.retrieval.vector_results and len(result.warnings) >= 2:
        raise HTTPException(status_code=503, detail={"code": "RETRIEVAL_UNAVAILABLE", "message": "Both retrieval systems are unavailable", "details": {"warnings": result.warnings}})
    return result


@router.post("/query-plan", response_model=QueryPlan)
async def query_plan(request: QuestionRequest) -> QueryPlan:
    return QueryPlan(intent=classify_intent(request.question), entity_mentions=extract_entity_mentions(request.question), max_hops=3 if "multi_hop" in classify_intent(request.question) else 1)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: QuestionRequest, settings: Settings = Depends(get_settings), retriever: HybridRetriever = Depends(get_retriever), ollama: OllamaService = Depends(get_ollama)) -> ChatResponse:
    CHAT_REQUESTS.inc(); RETRIEVAL_MODES.labels(request.mode).inc()
    previous_user_question = next((turn.content for turn in reversed(request.history) if turn.role == "user"), "")
    retrieval_question = f"{previous_user_question} {request.question}" if previous_user_question else request.question
    with RETRIEVAL_LATENCY.labels(request.mode).time():
        result = await retriever.retrieve(retrieval_question, request.mode)
    result.question = request.question
    confidence = OntologyService.confidence(result)
    if not result.retrieval.graph_facts and not result.retrieval.vector_results:
        ANSWER_STATUS.labels("insufficient_evidence").inc()
        return ChatResponse(**result.model_dump(), answer=localized_message(request.question, "insufficient"), answer_status="insufficient_evidence", confidence=0)
    ambiguity_answer = OntologyService.ambiguity_answer(result)
    if ambiguity_answer:
        result.retrieval.timings_ms["generation"] = 0.0
        ANSWER_STATUS.labels("answered").inc()
        return ChatResponse(
            **result.model_dump(),
            answer=ambiguity_answer,
            answer_status="answered",
            confidence=confidence,
        )
    context = build_context(
        result.entities,
        result.retrieval.graph_facts,
        result.retrieval.vector_results,
        result.sources,
        settings.max_context_items,
        settings.max_context_characters,
        request.question,
    )
    started = time.perf_counter()
    try:
        history_context = "\n".join(f"{turn.role.title()}: {turn.content}" for turn in request.history[-6:])
        grounded_context = f"Recent conversation (for reference resolution only):\n{history_context}\n\n{context}" if history_context else context
        with OLLAMA_LATENCY.time(): answer = await ollama.generate(request.question, grounded_context)
        result.retrieval.timings_ms["generation"] = round((time.perf_counter()-started)*1000, 2)
        ANSWER_STATUS.labels("answered").inc()
        return ChatResponse(**result.model_dump(), answer=answer, answer_status="answered", confidence=confidence)
    except Exception as exc:
        CHAT_FAILURES.inc(); ANSWER_STATUS.labels("partial").inc()
        result.warnings.append(f"Generation unavailable: {exc}")
        return ChatResponse(**result.model_dump(), answer=localized_message(request.question, "partial"), answer_status="partial", confidence=max(0.1, confidence - 0.2))
