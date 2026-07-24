from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.graph import GraphData

RetrievalMode = Literal["vector_only", "graph_only", "hybrid"]


class RetrievalItem(BaseModel):
    id: str
    entity_uri: str
    entity_type: str = "Thing"
    label: str
    text: str
    source: str
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphFact(BaseModel):
    id: str
    subject: str
    subject_label: str
    predicate: str
    predicate_label: str
    object: str
    object_label: str
    score: float = 1.0


class QueryPlan(BaseModel):
    intent: list[str] = Field(default_factory=lambda: ["unknown"])
    entity_mentions: list[str] = Field(default_factory=list, max_length=20)
    relationship_hints: list[str] = Field(default_factory=list, max_length=20)
    requested_fields: list[str] = Field(default_factory=list, max_length=20)
    max_hops: int = Field(2, ge=1, le=3)


class RetrievalDetails(BaseModel):
    vector_results: list[RetrievalItem] = Field(default_factory=list)
    graph_facts: list[GraphFact] = Field(default_factory=list)
    timings_ms: dict[str, float] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    question: str
    intent: list[str]
    entities: list[RetrievalItem] = Field(default_factory=list)
    graph: GraphData = Field(default_factory=GraphData)
    sources: list[str] = Field(default_factory=list)
    retrieval: RetrievalDetails = Field(default_factory=RetrievalDetails)
    warnings: list[str] = Field(default_factory=list)

