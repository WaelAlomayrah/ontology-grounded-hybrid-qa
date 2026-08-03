from functools import lru_cache

from fastapi import Depends, Header, HTTPException

from app.config import Settings, get_settings
from app.embedding_models import settings_for_index
from app.retrieval.hybrid_retriever import HybridRetriever
from app.services.embedding_service import EmbeddingService
from app.services.fuseki_service import FusekiService
from app.services.milvus_service import MilvusService
from app.services.ollama_service import OllamaService
from app.services.workspace_state import active_dataset, active_embedding_model


def get_fuseki() -> FusekiService:
    return FusekiService(get_settings(), active_dataset())


@lru_cache
def get_milvus() -> MilvusService:
    return MilvusService(get_settings())


@lru_cache
def get_embeddings() -> EmbeddingService:
    return EmbeddingService(get_settings())


@lru_cache
def get_ollama() -> OllamaService:
    return OllamaService(get_settings())


def get_retriever() -> HybridRetriever:
    settings = settings_for_index(get_settings(), active_dataset(), active_embedding_model())
    return HybridRetriever(
        settings, get_fuseki(), MilvusService(settings), EmbeddingService(settings)
    )


def require_admin(
    x_admin_token: str = Header(default=""), settings: Settings = Depends(get_settings)
) -> None:
    if not x_admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ADMIN_TOKEN_REQUIRED",
                "message": "Valid X-Admin-Token required",
                "details": {},
            },
        )
