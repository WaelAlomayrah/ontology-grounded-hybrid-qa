import json
from pathlib import Path
from typing import Any

from rdflib import OWL, RDF, Graph, URIRef

ARABIC_BASE = "http://example.org/arabic-enterprise/"
MAX_DOCUMENTS = 5_000


def load_arabic_enterprise(directory: Path) -> tuple[Graph, int, int, list[str], list[dict[str, Any]]]:
    graph_path = directory / "knowledge_graph.ttl"
    documents_path = directory / "documents.jsonl"
    if not graph_path.is_file():
        raise FileNotFoundError("Arabic Enterprise knowledge_graph.ttl was not found")
    if not documents_path.is_file():
        raise FileNotFoundError("Arabic Enterprise documents.jsonl was not found")

    graph = Graph()
    graph.parse(graph_path, format="turtle")
    schema_types = {OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.Ontology}
    entities = len({
        subject
        for subject, entity_type in graph.subject_objects(RDF.type)
        if isinstance(subject, URIRef) and entity_type not in schema_types
    })
    relationships = sum(
        1
        for subject, predicate, value in graph
        if isinstance(subject, URIRef) and isinstance(value, URIRef) and predicate != RDF.type
    )

    documents: list[dict[str, Any]] = []
    with documents_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            if len(documents) >= MAX_DOCUMENTS:
                raise ValueError(f"Arabic document limit exceeded ({MAX_DOCUMENTS})")
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in documents.jsonl at line {line_number}") from exc
            identifier = str(row.get("id", "")).strip()
            title = str(row.get("title", "")).strip()
            body = str(row.get("body", "")).strip()
            if not identifier or not title or not body:
                raise ValueError(f"Arabic document line {line_number} is missing id, title, or body")
            entity_uri = f"{ARABIC_BASE}document/{identifier}"
            documents.append({
                "id": identifier,
                "entity_uri": entity_uri,
                "entity_type": "Document",
                "label": title,
                "text": (
                    f"العنوان: {title}\n"
                    f"نوع المستند: {row.get('document_type', '')}\n"
                    f"التصنيف: {row.get('classification', '')}\n"
                    f"المحتوى: {body}"
                ),
                "source": "arabic_enterprise",
                "metadata": {
                    "department_id": row.get("department_id", ""),
                    "author_id": row.get("author_id", ""),
                    "system_id": row.get("system_id", ""),
                    "project_id": row.get("project_id", ""),
                    "created_at": row.get("created_at", ""),
                },
            })
    warnings = [] if documents else ["No Arabic documents were available for semantic indexing"]
    return graph, entities, relationships, warnings, documents
