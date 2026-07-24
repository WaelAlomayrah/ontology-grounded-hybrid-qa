from app.models.retrieval import RetrievalResult


class OntologyService:
    @staticmethod
    def confidence(result: RetrievalResult) -> float:
        evidence = len(result.retrieval.graph_facts) + len(result.retrieval.vector_results)
        diversity = int(bool(result.retrieval.graph_facts)) + int(bool(result.retrieval.vector_results))
        return round(min(0.95, 0.15 + min(evidence, 8) * 0.07 + diversity * 0.1), 2) if evidence else 0.0

