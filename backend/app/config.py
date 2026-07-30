from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration sourced exclusively from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: str = "development"
    log_level: str = "INFO"
    backend_port: int = 8000
    frontend_port: int = 3000
    cors_origins: list[str] | str = ["http://localhost:3000"]
    admin_token: str = "change-me-development-only"
    fuseki_base_url: str = "http://fuseki:3030"
    fuseki_dataset: str = "ontology"
    fuseki_user: str = "admin"
    fuseki_password: str = "change-me-fuseki"
    milvus_host: str = "milvus"
    milvus_port: int = 19530
    milvus_collection: str = "ontology_documents"
    milvus_vector_dimension: int = 1024
    milvus_metric_type: str = "COSINE"
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "gemma3:4b"
    ollama_timeout_seconds: float = 120
    prometheus_base_url: str = "http://prometheus:9090"
    docker_proxy_base_url: str = "http://docker-proxy:2375"
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 16
    embedding_normalize: bool = True
    dataset_path: Path = Path("/app/data/KG2QA_ontology_dataset")
    northwind_dataset_path: Path = Path("/app/data/Northwind_dataset")
    arabic_enterprise_dataset_path: Path = Path("/app/data/Arabic_enterprise_dataset")
    ontology_file: Path = Path("/app/data/sample/ontology.ttl")
    vector_top_k: int = Field(8, ge=1, le=100)
    graph_result_limit: int = Field(100, ge=1, le=1000)
    hybrid_vector_weight: float = Field(0.55, ge=0, le=1)
    hybrid_graph_weight: float = Field(0.45, ge=0, le=1)
    max_context_items: int = Field(30, ge=1, le=200)
    max_context_characters: int = Field(12000, ge=1000, le=100000)
    max_question_length: int = Field(1000, ge=10, le=10000)
    enable_llm_query_planner: bool = False
    enable_sample_fallback: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        return [v.strip() for v in value.split(",") if v.strip()] if isinstance(value, str) else value

    @field_validator("milvus_metric_type")
    @classmethod
    def validate_metric(cls, value: str) -> str:
        value = value.upper()
        if value != "COSINE":
            raise ValueError("This pilot requires COSINE similarity")
        return value

    @model_validator(mode="after")
    def validate_weights(self) -> "Settings":
        if abs(self.hybrid_vector_weight + self.hybrid_graph_weight - 1.0) > 1e-6:
            raise ValueError("Hybrid weights must sum to 1.0")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
