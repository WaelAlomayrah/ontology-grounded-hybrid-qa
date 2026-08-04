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
    milvus_operation_retries: int = Field(5, ge=1, le=10)
    milvus_retry_backoff_seconds: float = Field(1.0, ge=0.1, le=30)
    milvus_flush_interval: int = Field(4096, ge=64, le=65536)
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
    policeuk_enabled: bool = True
    policeuk_force: str = "Thames Valley Police"
    policeuk_months: int = Field(12, ge=1, le=36)
    policeuk_raw_dir: Path = Path("/app/data/policeuk/raw")
    policeuk_processed_dir: Path = Path("/app/data/policeuk/processed")
    policeuk_download: bool = True
    policeuk_include_crimes: bool = True
    policeuk_include_outcomes: bool = True
    policeuk_include_stops: bool = True
    policeuk_include_neighbourhoods: bool = True
    policeuk_include_ons_population: bool = True
    policeuk_archive_url: str = "https://data.police.uk/data/archive/latest.zip"
    policeuk_ons_population_url: str = (
        "https://www.nomisweb.co.uk/api/v01/dataset/NM_2014_1.data.csv"
    )
    policeuk_http_timeout_seconds: float = Field(60, ge=5, le=3600)
    policeuk_http_retries: int = Field(3, ge=0, le=10)
    policeuk_api_delay_seconds: float = Field(0.1, ge=0, le=5)
    policeuk_user_agent: str = "ontology-grounded-hybrid-qa/0.1 (public-safety research)"
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
