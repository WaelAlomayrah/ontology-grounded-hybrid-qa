import asyncio
import time

from app.config import Settings
from app.models.retrieval import RetrievalDetails, RetrievalItem, RetrievalResult
from app.retrieval.intent_classifier import classify_intent, extract_entity_mentions
from app.services.embedding_service import EmbeddingService
from app.services.fuseki_service import FusekiService
from app.services.milvus_service import MilvusService


def hybrid_score(vector_score: float, graph_score: float, vector_weight: float, graph_weight: float) -> float:
    return max(0.0, min(1.0, vector_weight * max(0.0, min(1.0, vector_score)) + graph_weight * max(0.0, min(1.0, graph_score))))


def deduplicate_results(items: list[RetrievalItem]) -> list[RetrievalItem]:
    by_uri: dict[str, RetrievalItem] = {}
    for item in items:
        key = item.entity_uri or item.id
        if key not in by_uri or item.score > by_uri[key].score:
            by_uri[key] = item
    return sorted(by_uri.values(), key=lambda item: item.score, reverse=True)


class HybridRetriever:
    def __init__(self, settings: Settings, fuseki: FusekiService, milvus: MilvusService, embeddings: EmbeddingService) -> None:
        self.settings, self.fuseki, self.milvus, self.embeddings = settings, fuseki, milvus, embeddings

    async def retrieve(self, question: str, mode: str = "hybrid") -> RetrievalResult:
        started = time.perf_counter()
        intents, mentions = classify_intent(question), extract_entity_mentions(question)
        warnings: list[str] = []
        graph, facts, vectors = None, [], []
        graph_ms = vector_ms = 0.0
        if mode != "vector_only":
            mark = time.perf_counter()
            try:
                search_terms = mentions or [question]
                graph, facts = await self.fuseki.facts_for_labels(search_terms)
            except Exception as exc:
                warnings.append(f"Graph retrieval unavailable: {exc}")
            graph_ms = (time.perf_counter() - mark) * 1000
        if mode != "graph_only":
            mark = time.perf_counter()
            try:
                vector = (await asyncio.to_thread(self.embeddings.encode_queries, [question]))[0]
                vectors = await asyncio.to_thread(self.milvus.search, vector, self.settings.vector_top_k)
            except Exception as exc:
                warnings.append(f"Vector retrieval unavailable: {exc}")
            vector_ms = (time.perf_counter() - mark) * 1000
        entities = deduplicate_results(vectors)
        if graph:
            graph_entities = [RetrievalItem(id=node.id, entity_uri=node.id, entity_type=node.type, label=node.label, text=f"Entity: {node.label}; Type: {node.type}", source="fuseki", score=self.settings.hybrid_graph_weight) for node in graph.nodes]
            entities = deduplicate_results(entities + graph_entities)
        from app.models.graph import GraphData
        return RetrievalResult(question=question, intent=intents, entities=entities[:self.settings.max_context_items], graph=graph or GraphData(), sources=sorted({item.source for item in entities} | ({"fuseki"} if facts else set())), retrieval=RetrievalDetails(vector_results=vectors, graph_facts=facts, timings_ms={"graph": round(graph_ms, 2), "vector": round(vector_ms, 2), "total": round((time.perf_counter()-started)*1000, 2)}), warnings=warnings)

