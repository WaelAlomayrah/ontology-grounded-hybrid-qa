from collections.abc import Sequence

from app.config import Settings


class EmbeddingService:
    """Lazy sentence-transformer wrapper with E5 query/passage conventions."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: object | None = None
        self.dimension: int | None = None

    def _get_model(self):  # type: ignore[no-untyped-def]
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.settings.embedding_model, device=self.settings.embedding_device
            )
            self._model.max_seq_length = 512
            transformer = self._model[0]
            auto_model = getattr(transformer, "auto_model", None)
            if auto_model is not None and hasattr(auto_model.config, "reference_compile"):
                auto_model.config.reference_compile = False
            reported_dimension = self._model.get_sentence_embedding_dimension()
            if reported_dimension is None:
                raise ValueError("Embedding model did not report an output dimension")
            self.dimension = int(reported_dimension)
            if self.dimension != self.settings.milvus_vector_dimension:
                raise ValueError(
                    f"Embedding dimension {self.dimension} differs from configured "
                    f"MILVUS_VECTOR_DIMENSION={self.settings.milvus_vector_dimension}"
                )
        return self._model

    def encode_queries(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode([self._prefix("query", value) for value in texts])

    def encode_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode([self._prefix("passage", value) for value in texts])

    def _prefix(self, kind: str, text: str) -> str:
        return f"{kind}: {text}" if "e5" in self.settings.embedding_model.lower() else text

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._get_model().encode(
            texts,
            batch_size=self.settings.embedding_batch_size,
            normalize_embeddings=self.settings.embedding_normalize,
        )
        return vectors.tolist()
