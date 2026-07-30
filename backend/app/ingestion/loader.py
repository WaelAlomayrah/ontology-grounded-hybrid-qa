import argparse
import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rdflib import RDF, RDFS, Graph, URIRef

from app.config import Settings, get_settings
from app.embedding_models import settings_for_index
from app.ingestion.arabic_enterprise_loader import load_arabic_enterprise
from app.ingestion.csv_loader import load_csv_connector
from app.ingestion.kg2qa_loader import discover_files, load_kg2qa
from app.ingestion.northwind_loader import load_northwind
from app.ingestion.sample_loader import build_sample_graph
from app.metrics import INGESTION_ENTITIES, INGESTION_FAILURES, INGESTION_RELATIONSHIPS
from app.models.api import IngestionReport
from app.services.embedding_service import EmbeddingService
from app.services.fuseki_service import FusekiService
from app.services.milvus_service import MilvusService

logger = logging.getLogger(__name__)
latest_report: IngestionReport | None = None


def entity_documents(graph: Graph, source: str) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for subject in sorted({s for s in graph.subjects() if isinstance(s, URIRef)}, key=str):
        labels = sorted(str(value) for value in graph.objects(subject, RDFS.label))
        types = sorted(str(value) for value in graph.objects(subject, RDF.type))
        if not labels or not types:
            continue
        label = labels[0]
        entity_type = types[0].rsplit("/", 1)[-1]
        description_predicates = sorted(
            {
                predicate
                for predicate in graph.predicates(subject)
                if str(predicate).endswith("description")
            },
            key=str,
        )
        descriptions = sorted(
            str(value)
            for predicate in description_predicates
            for value in graph.objects(subject, predicate)
        )
        relationships = []
        for predicate, obj in sorted(
            graph.predicate_objects(subject), key=lambda pair: (str(pair[0]), str(pair[1]))
        ):
            if isinstance(obj, URIRef) and predicate not in {RDF.type}:
                target_labels = sorted(str(value) for value in graph.objects(obj, RDFS.label))
                target_label = target_labels[0] if target_labels else str(obj).rsplit("/", 1)[-1]
                relationships.append(f"{str(predicate).rsplit('/', 1)[-1]} {target_label}")
        text = f"Entity: {label}\nType: {entity_type}\nDescription: {'; '.join(descriptions) or 'Not provided'}\nRelationships: {'; '.join(relationships) or 'None'}"
        documents.append(
            {
                "id": hashlib.sha256(f"{source}|{subject}".encode()).hexdigest()[:32],
                "entity_uri": str(subject),
                "entity_type": entity_type,
                "label": label,
                "text": text,
                "source": source,
                "metadata": {"relationships": len(relationships)},
            }
        )
    return documents


def _failure_message(stage: str, exc: Exception) -> str:
    """Return a useful message even for exceptions whose string value is empty."""
    detail = str(exc).strip() or repr(exc).strip() or "No error detail was provided"
    return f"{stage}: {type(exc).__name__}: {detail}"


def _vector_cache_path(directory: Path, model_id: str) -> Path:
    return directory / "precomputed_vectors" / f"{model_id}.jsonl"


def _load_vector_cache(path: Path, dimension: int) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    cached: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
                if len(row.get("embedding", [])) == dimension:
                    cached[str(row["id"])] = row
            except (ValueError, KeyError, TypeError):
                continue
    return cached


def _save_vector_cache(path: Path, documents: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for document in documents:
            row = {
                "id": document["id"],
                "content_hash": document["content_hash"],
                "embedding": document["embedding"],
            }
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(path)


async def ingest(
    dataset: str,
    reset: bool,
    load_graph: bool,
    load_vectors: bool,
    settings: Settings | None = None,
    progress: Callable[[str, int], None] | None = None,
    embedding_model: str = "e5-large",
    embedding_device: str | None = None,
    embedding_batch_size: int | None = None,
    incremental: bool = True,
    use_precomputed: bool = True,
    save_precomputed: bool = False,
) -> IngestionReport:
    global latest_report
    settings = settings or get_settings()
    started = time.perf_counter()
    selected = dataset.lower()
    warnings: list[str] = []
    sample_dir = settings.ontology_file.parent
    prepared_documents: list[dict[str, Any]] | None = None
    dataset_directory = sample_dir
    if selected == "kg2qa" and not (
        any(discover_files(settings.dataset_path).values())
        or any(settings.dataset_path.glob("*.zip"))
    ):
        if not settings.enable_sample_fallback:
            raise FileNotFoundError(f"No KG2QA files found in {settings.dataset_path}")
        warnings.append(f"KG2QA absent at {settings.dataset_path}; loaded sample dataset")
        selected = "sample"
    if selected == "sample":
        graph, entities, relationships = build_sample_graph(sample_dir)
        rdf_count = 1
    elif selected == "kg2qa":
        dataset_directory = settings.dataset_path
        graph, entities, relationships, detected_warnings = load_kg2qa(settings.dataset_path)
        warnings.extend(detected_warnings)
        rdf_count = len(discover_files(settings.dataset_path)["rdf"])
    elif selected == "northwind":
        dataset_directory = settings.northwind_dataset_path
        graph, entities, relationships, detected_warnings = load_northwind(
            settings.northwind_dataset_path
        )
        warnings.extend(detected_warnings)
        rdf_count = 0
    elif selected == "arabic_enterprise":
        dataset_directory = settings.arabic_enterprise_dataset_path
        graph, entities, relationships, detected_warnings, prepared_documents = (
            load_arabic_enterprise(settings.arabic_enterprise_dataset_path)
        )
        warnings.extend(detected_warnings)
        rdf_count = 2
    elif selected.startswith("csv:"):
        connector_id = selected.removeprefix("csv:")
        if len(connector_id) != 36 or any(
            character not in "0123456789abcdef-" for character in connector_id
        ):
            raise ValueError("Invalid CSV connector identifier")
        connector_path = Path("/app/data/runtime/connectors") / connector_id
        if not connector_path.is_dir():
            raise FileNotFoundError("CSV connector not found")
        dataset_directory = connector_path
        graph, entities, relationships, detected_warnings = load_csv_connector(
            connector_path, connector_id
        )
        warnings.extend(detected_warnings)
        rdf_count = 0
    else:
        raise ValueError(
            "dataset must be sample, kg2qa, northwind, arabic_enterprise, or a CSV connector"
        )
    index_settings = settings_for_index(
        settings,
        selected,
        embedding_model,
        embedding_device,
        embedding_batch_size,
    )
    report = IngestionReport(
        dataset_selected=selected,
        rdf_files_loaded=rdf_count,
        entities_processed=entities,
        relationships_processed=relationships,
        warnings=warnings,
        embedding_model=embedding_model,
        embedding_device=index_settings.embedding_device,
        collection=index_settings.milvus_collection,
    )
    if progress:
        progress("mapped", 25)
    stage = "preparing ingestion"
    try:
        if load_graph:
            stage = "resetting Fuseki graph" if reset else "uploading Fuseki graph"
            fuseki = FusekiService(settings)
            if reset:
                await fuseki.delete_all()
                stage = "uploading Fuseki graph"
            await fuseki.upload_rdf(graph.serialize(format="turtle", encoding="utf-8"))
            if progress:
                progress("graph_loaded", 55)
        if load_vectors:
            stage = "preparing vector documents"
            embeddings, milvus = EmbeddingService(index_settings), MilvusService(index_settings)
            graph_documents = entity_documents(graph, selected)
            if prepared_documents is None:
                documents = graph_documents
            else:
                by_uri = {document["entity_uri"]: document for document in graph_documents}
                by_uri.update({document["entity_uri"]: document for document in prepared_documents})
                documents = list(by_uri.values())
            stage = "preparing Milvus collection"
            await asyncio.to_thread(
                milvus.ensure_collection, index_settings.milvus_vector_dimension
            )
            if reset:
                stage = "recreating isolated Milvus collection"
                await asyncio.to_thread(milvus.drop_collection)
                await asyncio.to_thread(
                    milvus.ensure_collection, index_settings.milvus_vector_dimension
                )
            for document in documents:
                document["content_hash"] = hashlib.sha256(
                    document["text"].encode("utf-8")
                ).hexdigest()
            existing = (
                {}
                if reset or not incremental
                else await asyncio.to_thread(milvus.existing_hashes, selected)
            )
            unchanged = [
                document
                for document in documents
                if existing.get(document["id"]) == document["content_hash"]
            ]
            changed = [
                document
                for document in documents
                if existing.get(document["id"]) != document["content_hash"]
            ]
            report.skipped_records = len(unchanged)
            report.vectors_reused = len(unchanged)

            cache_path = _vector_cache_path(dataset_directory, embedding_model)
            cached = (
                _load_vector_cache(cache_path, index_settings.milvus_vector_dimension)
                if use_precomputed
                else {}
            )
            cached_documents: list[dict[str, Any]] = []
            to_encode: list[dict[str, Any]] = []
            for document in changed:
                cached_row = cached.get(document["id"])
                if cached_row and cached_row.get("content_hash") == document["content_hash"]:
                    document["embedding"] = cached_row["embedding"]
                    cached_documents.append(document)
                else:
                    to_encode.append(document)
            if cached_documents:
                stage = "writing precomputed Milvus vectors"
                await asyncio.to_thread(
                    milvus.upsert_documents, cached_documents, index_settings.embedding_batch_size
                )
                report.vectors_reused += len(cached_documents)

            generated_documents: list[dict[str, Any]] = []
            batch_size = index_settings.embedding_batch_size
            total_batches = max(1, (len(to_encode) + batch_size - 1) // batch_size)
            for offset in range(0, len(to_encode), batch_size):
                batch = to_encode[offset : offset + batch_size]
                stage = "generating embedding batch"
                vectors = await asyncio.to_thread(
                    embeddings.encode_passages, [document["text"] for document in batch]
                )
                for document, vector in zip(batch, vectors, strict=True):
                    document["embedding"] = vector
                stage = "writing Milvus vector batch"
                await asyncio.to_thread(milvus.upsert_documents, batch, batch_size)
                generated_documents.extend(batch)
                report.vectors_generated += len(batch)
                if progress:
                    completed = offset // batch_size + 1
                    progress("embedding_batches", 55 + round(40 * completed / total_batches))
            if save_precomputed and (generated_documents or cached_documents):
                stage = "saving precomputed vector cache"
                cache_rows = [*unchanged, *cached_documents, *generated_documents]
                # Unchanged vectors are already in Milvus but are not loaded here; retain
                # their previous cache rows when available.
                cached_by_id = {key: value for key, value in cached.items()}
                complete_cache: list[dict[str, Any]] = []
                for document in cache_rows:
                    if "embedding" not in document and document["id"] in cached_by_id:
                        document["embedding"] = cached_by_id[document["id"]]["embedding"]
                    if "embedding" in document:
                        complete_cache.append(document)
                _save_vector_cache(cache_path, complete_cache)
            stage = "finalizing Milvus vectors"
            await asyncio.to_thread(milvus.flush)
            expected_hashes = {document["id"]: document["content_hash"] for document in documents}
            await asyncio.to_thread(milvus.wait_until_source_visible, selected, expected_hashes)
            if progress:
                progress("indexed", 95)
    except Exception as exc:
        INGESTION_FAILURES.labels(selected).inc()
        message = _failure_message(stage, exc)
        report.errors.append(message)
        report.failed_records += 1
        logger.exception(
            "ingestion_failed",
            extra={
                "event": "ingestion_failed",
                "status": "error",
                "stage": stage,
                "exception_type": type(exc).__name__,
            },
        )
    INGESTION_ENTITIES.labels(selected).inc(report.entities_processed)
    INGESTION_RELATIONSHIPS.labels(selected).inc(report.relationships_processed)
    report.elapsed_time = round(time.perf_counter() - started, 3)
    latest_report = report
    if progress:
        progress("complete" if not report.errors else "failed", 100)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Idempotent ontology pilot data loader")
    parser.add_argument(
        "--dataset", choices=("sample", "kg2qa", "northwind", "arabic_enterprise"), default="sample"
    )
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--load-graph", action="store_true")
    parser.add_argument("--load-vectors", action="store_true")
    parser.add_argument(
        "--embedding-model",
        choices=("e5-large", "granite-311m-r2", "granite-97m-r2"),
        default="e5-large",
    )
    parser.add_argument("--embedding-device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--embedding-batch-size", type=int, choices=(16, 32, 64, 128), default=16)
    parser.add_argument("--full-vector-rebuild", action="store_true")
    parser.add_argument("--save-precomputed", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = asyncio.run(
        ingest(
            args.dataset,
            args.reset,
            args.load_graph,
            args.load_vectors,
            embedding_model=args.embedding_model,
            embedding_device=args.embedding_device,
            embedding_batch_size=args.embedding_batch_size,
            incremental=not args.full_vector_rebuild,
            save_precomputed=args.save_precomputed,
        )
    )
    print(report.model_dump_json(indent=2))
    if report.errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
