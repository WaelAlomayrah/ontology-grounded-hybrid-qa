from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.models.retrieval import RetrievalMode, RetrievalResult


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    mode: RetrievalMode = "hybrid"
    history: list["ConversationTurn"] = Field(default_factory=list, max_length=8)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Question cannot be blank")
        return normalized


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatResponse(RetrievalResult):
    answer: str
    answer_status: Literal["answered", "partial", "insufficient_evidence", "error"]
    confidence: float = Field(ge=0, le=1)


class PathRequest(BaseModel):
    source_uri: str
    target_uri: str
    max_hops: int = Field(3, ge=1, le=3)


class IngestionRequest(BaseModel):
    mode: Literal["reset", "append"] = "append"
    load_graph: bool = True
    load_vectors: bool = True
    embedding_model: Literal["e5-large", "granite-311m-r2", "granite-97m-r2"] = "e5-large"
    embedding_device: Literal["cpu", "cuda"] = "cpu"
    embedding_batch_size: Literal[16, 32, 64, 128] = 16
    incremental: bool = True
    use_precomputed: bool = True
    save_precomputed: bool = False


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class MappingColumn(BaseModel):
    source: str
    target: str
    role: Literal["identifier", "label", "attribute", "source", "target", "predicate", "ignore"]


class ObjectMapping(BaseModel):
    dataset: str
    source: str
    target_class: str
    mapping_kind: Literal["entity", "relationship"]
    columns: list[MappingColumn]


class MappingProfileRequest(BaseModel):
    dataset: str
    mappings: list[ObjectMapping] = Field(max_length=200)


class IngestionJobRequest(IngestionRequest):
    dataset: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^(sample|kg2qa|northwind|arabic_enterprise|policeuk|csv:[0-9a-f-]{36})$",
    )
    download: bool | None = None
    force: str | None = Field(default=None, max_length=120)
    months: int | None = Field(default=None, ge=1, le=36)


class EvaluationRunRequest(BaseModel):
    dataset: Literal["sample", "kg2qa", "arabic_enterprise", "policeuk"]
    embedding_model: Literal["e5-large", "granite-311m-r2", "granite-97m-r2"]


class IngestionReport(BaseModel):
    dataset_selected: str
    rdf_files_loaded: int = 0
    entities_processed: int = 0
    relationships_processed: int = 0
    vectors_generated: int = 0
    vectors_reused: int = 0
    embedding_model: str = ""
    embedding_device: str = ""
    collection: str = ""
    failed_records: int = 0
    skipped_records: int = 0
    elapsed_time: float = 0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody
