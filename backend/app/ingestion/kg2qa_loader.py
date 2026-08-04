import json
from pathlib import Path
from urllib.parse import quote
from zipfile import ZipFile

import pandas as pd
from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef

from app.ingestion.mappings import (
    ID_COLUMNS,
    LABEL_COLUMNS,
    RELATION_COLUMNS,
    SOURCE_COLUMNS,
    TARGET_COLUMNS,
    detect_column,
)
from app.ingestion.rdf_loader import load_rdf_files

KG = Namespace("http://example.org/kg2qa/")


def _kg_uri(value: object) -> URIRef:
    """Create a stable, valid URI for identifiers found in legacy CSV files."""
    text = str(value).strip()
    if text.startswith(("http://", "https://")):
        return URIRef(quote(text, safe=":/?#[]@!$&'()*+,;=-._~%"))
    return URIRef(f"{KG}{quote(text, safe='-._~')}")


def _predicate_uri(value: object) -> URIRef:
    text = str(value).strip().replace(" ", "_") or "relatedTo"
    return URIRef(f"{KG}{quote(text, safe='-._~')}")


def _read_csv(source: object, filename: str, warnings: list[str]) -> pd.DataFrame:
    try:
        return pd.read_csv(source).fillna("")
    except pd.errors.ParserError:
        warnings.append(f"Skipped malformed legacy rows in {filename}")
        if hasattr(source, "seek"):
            source.seek(0)
        return pd.read_csv(source, engine="python", on_bad_lines="skip").fillna("")


def discover_files(directory: Path) -> dict[str, list[Path]]:
    files = [p for p in directory.rglob("*") if p.is_file() and p.name.lower() != "readme.md"] if directory.exists() else []
    return {
        "rdf": [p for p in files if p.suffix.lower() in {".rdf", ".ttl", ".owl"}],
        "csv": [p for p in files if p.suffix.lower() == ".csv"],
        "qa": [p for p in files if p.suffix.lower() == ".json" or "qa" in p.stem.lower()],
        "text": [p for p in files if p.suffix.lower() in {".txt", ".md"}],
    }


def load_kg2qa(directory: Path) -> tuple[Graph, int, int, list[str]]:
    discovered = discover_files(directory)
    graph = load_rdf_files(discovered["rdf"])
    entities = relationships = 0
    warnings: list[str] = []
    frames: list[tuple[str, pd.DataFrame]] = [
        (path.name, _read_csv(path, path.name, warnings)) for path in discovered["csv"]
    ]
    for archive in directory.rglob("*.zip"):
        with ZipFile(archive) as zipped:
            for name in zipped.namelist():
                if not name.lower().endswith(".csv"): continue
                frame = _read_csv(zipped.open(name), Path(name).name, warnings)
                frames.append((Path(name).name, frame))
    for filename, frame in frames:
        columns = list(frame.columns)
        normalized_columns = {column.strip().lower(): column for column in columns}
        source = detect_column(columns, SOURCE_COLUMNS, required=False)
        target = detect_column(columns, TARGET_COLUMNS, required=False)
        relation = detect_column(columns, RELATION_COLUMNS, required=False)
        if source and target:
            for row in frame.to_dict("records"):
                predicate = str(row.get(relation, "relatedTo")) if relation else "relatedTo"
                graph.add((_kg_uri(row[source]), _predicate_uri(predicate), _kg_uri(row[target])))
                relationships += 1
            continue
        identifier = detect_column(columns, ID_COLUMNS, required=False)
        # KG2QA entity tables use ``name`` for the human-readable label and
        # ``LABEL`` for the ontology class code (ACT, FUN, IDEN, ...).
        # Generic label detection would otherwise choose LABEL and make every
        # entity appear under a repeated class code.
        label = normalized_columns.get("name") or detect_column(
            columns, LABEL_COLUMNS, required=False
        )
        class_column = normalized_columns.get("label")
        if identifier and label:
            for row in frame.to_dict("records"):
                uri = _kg_uri(row[identifier])
                class_name = str(row.get(class_column, "")).strip() if class_column else ""
                graph.add(
                    (
                        uri,
                        RDF.type,
                        _predicate_uri(class_name) if class_name else KG.Entity,
                    )
                )
                graph.add((uri, RDFS.label, Literal(row[label])))
                for key, value in row.items():
                    if value != "" and key not in {identifier, label, class_column}:
                        graph.add((uri, _predicate_uri(key), Literal(value)))
                entities += 1
        else:
            warnings.append(f"Skipped unrecognized CSV schema: {filename}")
    return graph, entities, relationships, warnings


def load_qa_records(path: Path) -> list[dict[str, object]]:
    if path.suffix.lower() == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else value.get("questions", [])
    return pd.read_csv(path).fillna("").to_dict("records")
