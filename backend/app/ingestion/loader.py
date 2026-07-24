import argparse
import asyncio
import hashlib
import logging
import time
from collections.abc import Callable
from typing import Any
from pathlib import Path

from rdflib import RDF, RDFS, Graph, URIRef

from app.config import Settings, get_settings
from app.ingestion.kg2qa_loader import discover_files, load_kg2qa
from app.ingestion.csv_loader import load_csv_connector
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
        labels = list(graph.objects(subject, RDFS.label))
        types = list(graph.objects(subject, RDF.type))
        if not labels or not types:
            continue
        label = str(labels[0]); entity_type = str(types[0]).rsplit("/", 1)[-1]
        descriptions = [str(value) for predicate in graph.predicates(subject) if str(predicate).endswith("description") for value in graph.objects(subject, predicate)]
        relationships = []
        for predicate, obj in graph.predicate_objects(subject):
            if isinstance(obj, URIRef) and predicate not in {RDF.type}:
                target_label = next((str(x) for x in graph.objects(obj, RDFS.label)), str(obj).rsplit("/", 1)[-1])
                relationships.append(f"{str(predicate).rsplit('/', 1)[-1]} {target_label}")
        text = f"Entity: {label}\nType: {entity_type}\nDescription: {'; '.join(descriptions) or 'Not provided'}\nRelationships: {'; '.join(relationships) or 'None'}"
        documents.append({"id": hashlib.sha256(f"{source}|{subject}".encode()).hexdigest()[:32], "entity_uri": str(subject), "entity_type": entity_type, "label": label, "text": text, "source": source, "metadata": {"relationships": len(relationships)}})
    return documents


async def ingest(dataset: str, reset: bool, load_graph: bool, load_vectors: bool, settings: Settings | None = None, progress: Callable[[str, int], None] | None = None) -> IngestionReport:
    global latest_report
    settings = settings or get_settings(); started = time.perf_counter()
    selected = dataset.lower(); warnings: list[str] = []
    sample_dir = settings.ontology_file.parent
    if selected == "kg2qa" and not (any(discover_files(settings.dataset_path).values()) or any(settings.dataset_path.glob("*.zip"))):
        if not settings.enable_sample_fallback:
            raise FileNotFoundError(f"No KG2QA files found in {settings.dataset_path}")
        warnings.append(f"KG2QA absent at {settings.dataset_path}; loaded sample dataset")
        selected = "sample"
    if selected == "sample":
        graph, entities, relationships = build_sample_graph(sample_dir)
        rdf_count = 1
    elif selected == "kg2qa":
        graph, entities, relationships, detected_warnings = load_kg2qa(settings.dataset_path)
        warnings.extend(detected_warnings); rdf_count = len(discover_files(settings.dataset_path)["rdf"])
    elif selected == "northwind":
        graph, entities, relationships, detected_warnings = load_northwind(settings.northwind_dataset_path)
        warnings.extend(detected_warnings); rdf_count = 0
    elif selected.startswith("csv:"):
        connector_id = selected.removeprefix("csv:")
        if len(connector_id) != 36 or any(character not in "0123456789abcdef-" for character in connector_id):
            raise ValueError("Invalid CSV connector identifier")
        connector_path = Path("/app/data/runtime/connectors") / connector_id
        if not connector_path.is_dir():
            raise FileNotFoundError("CSV connector not found")
        graph, entities, relationships, detected_warnings = load_csv_connector(connector_path, connector_id)
        warnings.extend(detected_warnings); rdf_count = 0
    else:
        raise ValueError("dataset must be sample, kg2qa, northwind, or a CSV connector")
    report = IngestionReport(dataset_selected=selected, rdf_files_loaded=rdf_count, entities_processed=entities, relationships_processed=relationships, warnings=warnings)
    if progress: progress("mapped", 25)
    try:
        if load_graph:
            fuseki = FusekiService(settings)
            if reset: await fuseki.delete_all()
            await fuseki.upload_rdf(graph.serialize(format="turtle", encoding="utf-8"))
            if progress: progress("graph_loaded", 55)
        if load_vectors:
            embeddings, milvus = EmbeddingService(settings), MilvusService(settings)
            documents = entity_documents(graph, selected)
            vectors = await asyncio.to_thread(embeddings.encode_passages, [d["text"] for d in documents])
            if progress: progress("embedded", 80)
            dimension = len(vectors[0]) if vectors else settings.milvus_vector_dimension
            await asyncio.to_thread(milvus.ensure_collection, dimension)
            if reset: await asyncio.to_thread(milvus.delete_by_source, selected)
            for document, vector in zip(documents, vectors, strict=True): document["embedding"] = vector
            report.vectors_generated = await asyncio.to_thread(milvus.upsert_documents, documents)
            if progress: progress("indexed", 95)
    except Exception as exc:
        INGESTION_FAILURES.labels(selected).inc()
        report.errors.append(str(exc)); report.failed_records += 1
        logger.exception("ingestion_failed", extra={"event": "ingestion_failed", "status": "error"})
    INGESTION_ENTITIES.labels(selected).inc(report.entities_processed)
    INGESTION_RELATIONSHIPS.labels(selected).inc(report.relationships_processed)
    report.elapsed_time = round(time.perf_counter() - started, 3); latest_report = report
    if progress: progress("complete" if not report.errors else "failed", 100)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Idempotent ontology pilot data loader")
    parser.add_argument("--dataset", choices=("sample", "kg2qa", "northwind"), default="sample")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--load-graph", action="store_true")
    parser.add_argument("--load-vectors", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = asyncio.run(ingest(args.dataset, args.reset, args.load_graph, args.load_vectors))
    print(report.model_dump_json(indent=2))
    if report.errors: raise SystemExit(1)


if __name__ == "__main__":
    main()
