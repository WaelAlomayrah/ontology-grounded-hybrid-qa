from pathlib import Path

from rdflib import Graph

FORMATS = {".ttl": "turtle", ".rdf": "xml", ".owl": "xml"}


def load_rdf_files(files: list[Path]) -> Graph:
    graph = Graph()
    for path in files:
        try:
            graph.parse(path, format=FORMATS[path.suffix.lower()])
        except Exception:
            if path.suffix.lower() == ".owl":
                graph.parse(path)  # Some OWL files are Turtle despite their extension.
            else:
                raise
    return graph

