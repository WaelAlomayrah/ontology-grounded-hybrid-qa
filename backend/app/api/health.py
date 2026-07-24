import asyncio

from fastapi import APIRouter, Depends, Response, status

from app import __version__
from app.config import Settings, get_settings
from app.dependencies import get_fuseki, get_milvus, get_ollama
from app.ingestion.kg2qa_loader import discover_files
from app.services.fuseki_service import FusekiService
from app.services.milvus_service import MilvusService
from app.services.ollama_service import OllamaService

router = APIRouter()


async def service_status(fuseki: FusekiService, milvus: MilvusService, ollama: OllamaService, settings: Settings) -> dict[str, object]:
    fuseki_ok, milvus_ok, ollama_status = await asyncio.gather(fuseki.health_check(), asyncio.to_thread(milvus.health_check), ollama.health_check())
    has_kg2qa = any(discover_files(settings.dataset_path).values())
    return {"status": "healthy" if fuseki_ok or milvus_ok else "degraded", "dataset": "kg2qa" if has_kg2qa else "sample-fallback", "services": {"fuseki": fuseki_ok, "milvus": milvus_ok, "ollama": ollama_status}, "models": {"embedding": settings.embedding_model, "ollama": settings.ollama_model}}


@router.get("/")
async def root() -> dict[str, str]: return {"name": "Ontology AI Pilot", "docs": "/docs"}


@router.get("/health")
async def health(settings: Settings = Depends(get_settings), fuseki: FusekiService = Depends(get_fuseki), milvus: MilvusService = Depends(get_milvus), ollama: OllamaService = Depends(get_ollama)) -> dict[str, object]:
    return await service_status(fuseki, milvus, ollama, settings)


@router.get("/ready")
async def ready(response: Response, settings: Settings = Depends(get_settings), fuseki: FusekiService = Depends(get_fuseki), milvus: MilvusService = Depends(get_milvus), ollama: OllamaService = Depends(get_ollama)) -> dict[str, object]:
    result = await service_status(fuseki, milvus, ollama, settings)
    services = result["services"]
    ollama_healthy = bool(services["ollama"].get("healthy"))
    if not services["fuseki"] and not services["milvus"] and not ollama_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


@router.get("/version")
async def version() -> dict[str, str]: return {"version": __version__}
