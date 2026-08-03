import csv
import json
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

from rdflib import OWL, RDF, RDFS, Graph, Literal, Namespace, URIRef

from app.services.workspace_state import mapping_profile

ORG = Namespace("http://example.org/org/")
USER_DATA = Namespace("http://example.org/user-data/")
USER_ONTOLOGY = Namespace("http://example.org/user-ontology/")


def load_sample_csvs(directory: Path) -> tuple[Graph, int, int]:
    graph, entities, relationships = Graph(), 0, 0
    entity_files = {
        "departments.csv": (ORG.Department, {"location_id": ORG.locatedAt}),
        "employees.csv": (ORG.Employee, {"department_id": ORG.worksIn, "manages_department_id": ORG.manages, "location_id": ORG.locatedAt}),
        "locations.csv": (ORG.Location, {}),
        "projects.csv": (ORG.Project, {"sponsor_department_id": ORG.sponsoredBy, "system_id": ORG.usesSystem}),
        "systems.csv": (ORG.InformationSystem, {"owner_department_id": ORG.ownedBy, "vendor_id": ORG.suppliedBy}),
        "vendors.csv": (ORG.Vendor, {}),
    }
    for filename, (entity_type, relation_columns) in entity_files.items():
        with (directory / filename).open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                subject = ORG[row["id"]]
                graph.add((subject, RDF.type, entity_type))
                graph.add((subject, RDFS.label, Literal(row["label"])))
                for column in ("description", "email"):
                    if row.get(column):
                        graph.add((subject, ORG[column], Literal(row[column])))
                for column, predicate in relation_columns.items():
                    if row.get(column):
                        graph.add((subject, predicate, ORG[row[column]]))
                        relationships += 1
                entities += 1
    with (directory / "project_assignments.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            graph.add((ORG[row["employee_id"]], ORG.assignedTo, ORG[row["project_id"]]))
            relationships += 1
    return graph, entities, relationships


def load_csv_connector(directory: Path, connector_id: str) -> tuple[Graph, int, int, list[str]]:
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    mappings = mapping_profile(f"csv:{connector_id}") or []
    if not mappings:
        raise ValueError("CSV connector has no saved object mapping")
    mapping = cast(dict[str, Any], mappings[0])
    source_path = directory / str(metadata["stored_filename"])
    graph, entities, relationships = Graph(), 0, 0
    roles = {str(column["role"]): str(column["source"]) for column in mapping["columns"]}
    targets = {str(column["source"]): str(column["target"]) for column in mapping["columns"]}
    with source_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=str(metadata.get("delimiter", ",")))
        for row in reader:
            if mapping["mapping_kind"] == "relationship":
                source, target = row.get(roles.get("source", ""), "").strip(), row.get(roles.get("target", ""), "").strip()
                if not source or not target:
                    continue
                predicate = row.get(roles.get("predicate", ""), "").strip() or str(mapping["target_class"])
                predicate_uri = URIRef(f"{USER_ONTOLOGY}{quote(predicate, safe='-._~')}")
                graph.add((predicate_uri, RDF.type, OWL.ObjectProperty))
                graph.add((predicate_uri, RDFS.label, Literal(predicate)))
                graph.add(
                    (
                        URIRef(f"{USER_DATA}{quote(source, safe='-._~')}"),
                        predicate_uri,
                        URIRef(f"{USER_DATA}{quote(target, safe='-._~')}"),
                    )
                )
                relationships += 1
                continue
            identifier, label = row.get(roles.get("identifier", ""), "").strip(), row.get(roles.get("label", ""), "").strip()
            if not identifier or not label:
                continue
            subject = URIRef(f"{USER_DATA}{quote(identifier, safe='-._~')}")
            class_name = str(mapping["target_class"])
            class_uri = URIRef(f"{USER_ONTOLOGY}{quote(class_name, safe='-._~')}")
            graph.add((class_uri, RDF.type, OWL.Class))
            graph.add((class_uri, RDFS.label, Literal(class_name)))
            graph.add((subject, RDF.type, class_uri))
            graph.add((subject, RDFS.label, Literal(label)))
            for column in mapping["columns"]:
                source, role = str(column["source"]), str(column["role"])
                value = row.get(source, "")
                if role == "attribute" and value != "":
                    property_name = targets[source]
                    property_uri = URIRef(f"{USER_ONTOLOGY}{quote(property_name, safe='-._~')}")
                    graph.add((property_uri, RDF.type, OWL.DatatypeProperty))
                    graph.add((property_uri, RDFS.label, Literal(property_name)))
                    graph.add((property_uri, RDFS.domain, class_uri))
                    graph.add((subject, property_uri, Literal(value)))
            entities += 1
    return graph, entities, relationships, []
