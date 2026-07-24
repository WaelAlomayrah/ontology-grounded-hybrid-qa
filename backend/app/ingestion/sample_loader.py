from pathlib import Path

from rdflib import Graph

from app.ingestion.csv_loader import load_sample_csvs


def build_sample_graph(directory: Path) -> tuple[Graph, int, int]:
    ontology = Graph().parse(directory / "ontology.ttl", format="turtle")
    instances, entities, relationships = load_sample_csvs(directory)
    ontology += instances
    return ontology, entities, relationships

