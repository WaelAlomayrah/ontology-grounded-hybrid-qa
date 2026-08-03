import json
import time
from collections.abc import Iterable
from typing import Any, Callable, TypeVar

from pymilvus import DataType, MilvusClient

from app.config import Settings
from app.models.retrieval import RetrievalItem

T = TypeVar("T")


class MilvusService:
    """Thin Milvus client using deterministic document IDs for idempotent upserts."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: MilvusClient | None = None

    @property
    def client(self) -> MilvusClient:
        if self._client is None:
            self._client = MilvusClient(
                uri=f"http://{self.settings.milvus_host}:{self.settings.milvus_port}"
            )
        return self._client

    def health_check(self) -> bool:
        try:
            self.client.list_collections()
            return True
        except Exception:
            return False

    def _retry(self, operation: Callable[[], T]) -> T:
        last_error: Exception | None = None
        for attempt in range(self.settings.milvus_operation_retries):
            try:
                return operation()
            except Exception as exc:
                last_error = exc
                if attempt + 1 == self.settings.milvus_operation_retries:
                    break
                time.sleep(self.settings.milvus_retry_backoff_seconds * (2**attempt))
                self._client = None
        assert last_error is not None
        raise last_error

    def ensure_collection(self, dimension: int) -> None:
        if dimension != self.settings.milvus_vector_dimension:
            raise ValueError(
                f"Embedding dimension {dimension} does not match configured {self.settings.milvus_vector_dimension}"
            )
        name = self.settings.milvus_collection
        if self.client.has_collection(name):
            description = self.client.describe_collection(name)
            vector_field = next(
                field for field in description["fields"] if field["name"] == "embedding"
            )
            if int(vector_field["params"]["dim"]) != dimension:
                raise ValueError("Existing Milvus collection has a different vector dimension")
            return
        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("entity_uri", DataType.VARCHAR, max_length=2048)
        schema.add_field("entity_type", DataType.VARCHAR, max_length=256)
        schema.add_field("label", DataType.VARCHAR, max_length=1024)
        schema.add_field("text", DataType.VARCHAR, max_length=8192)
        schema.add_field("source", DataType.VARCHAR, max_length=512)
        schema.add_field("content_hash", DataType.VARCHAR, max_length=64)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=dimension)
        schema.add_field("metadata_json", DataType.VARCHAR, max_length=8192)
        index = self.client.prepare_index_params()
        index.add_index(
            "embedding",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 200},
        )
        self.client.create_collection(name, schema=schema, index_params=index)

    def upsert_documents(self, documents: Iterable[dict[str, Any]], batch_size: int = 100) -> int:
        batch: list[dict[str, Any]] = []
        total = 0
        for document in documents:
            item = dict(document)
            item["metadata_json"] = json.dumps(item.pop("metadata", {}), default=str)
            batch.append(item)
            if len(batch) >= batch_size:
                self._retry(lambda: self.client.upsert(self.settings.milvus_collection, batch))
                total += len(batch)
                batch = []
        if batch:
            self._retry(lambda: self.client.upsert(self.settings.milvus_collection, batch))
            total += len(batch)
        return total

    def search(self, vector: list[float], limit: int) -> list[RetrievalItem]:
        results = self.client.search(
            self.settings.milvus_collection,
            [vector],
            limit=min(limit, 100),
            output_fields=["entity_uri", "entity_type", "label", "text", "source", "metadata_json"],
            search_params={"metric_type": "COSINE", "params": {"ef": 64}},
        )[0]
        return [
            RetrievalItem(
                id=str(hit["id"]),
                score=float(hit["distance"]),
                metadata=json.loads(hit["entity"].get("metadata_json") or "{}"),
                **{
                    key: hit["entity"].get(key, "")
                    for key in ("entity_uri", "entity_type", "label", "text", "source")
                },
            )
            for hit in results
        ]

    def delete_by_source(self, source: str) -> None:
        safe = source.replace("\\", "\\\\").replace('"', '\\"')
        self.client.delete(self.settings.milvus_collection, filter=f'source == "{safe}"')
        self.client.flush(self.settings.milvus_collection)

    def flush(self) -> None:
        if self.client.has_collection(self.settings.milvus_collection):
            self._retry(lambda: self.client.flush(self.settings.milvus_collection))

    def wait_until_source_visible(
        self,
        source: str,
        expected: dict[str, str],
        timeout_seconds: float = 30.0,
    ) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            visible = self.existing_hashes(source)
            if all(
                visible.get(identifier) == content_hash
                for identifier, content_hash in expected.items()
            ):
                return
            time.sleep(0.2)
        raise TimeoutError("Milvus did not expose all written vector hashes within 30 seconds")

    def existing_hashes(self, source: str) -> dict[str, str]:
        if not self.client.has_collection(self.settings.milvus_collection):
            return {}
        safe = source.replace("\\", "\\\\").replace('"', '\\"')
        rows = self.client.query(
            self.settings.milvus_collection,
            filter=f'source == "{safe}"',
            output_fields=["id", "content_hash"],
            limit=16_384,
            consistency_level="Strong",
        )
        return {str(row["id"]): str(row.get("content_hash", "")) for row in rows}

    def existing_hashes_for_ids(self, identifiers: list[str]) -> dict[str, str]:
        if not identifiers or not self.client.has_collection(self.settings.milvus_collection):
            return {}
        rows = self.client.get(
            self.settings.milvus_collection,
            ids=identifiers,
            output_fields=["id", "content_hash"],
        )
        return {str(row["id"]): str(row.get("content_hash", "")) for row in rows}

    def count(self) -> int:
        if not self.client.has_collection(self.settings.milvus_collection):
            return 0
        stats = self._retry(
            lambda: self.client.get_collection_stats(self.settings.milvus_collection)
        )
        return int(stats["row_count"])

    def drop_collection(self) -> None:
        if self.client.has_collection(self.settings.milvus_collection):
            self.client.drop_collection(self.settings.milvus_collection)
