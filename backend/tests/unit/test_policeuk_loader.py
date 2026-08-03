import csv
import json
from pathlib import Path

import pytest
from rdflib import RDF, URIRef

from app.config import Settings
from app.ingestion.loader import _document_batches
from app.ingestion.policeuk_loader import (
    DATA,
    PUK,
    assign_neighbourhood,
    build_policeuk_graph,
    crime_id,
    filter_rows_to_months,
    normalize_force,
    normalize_lsoa,
    parse_population_rows,
    point_in_polygon,
    select_archive_members,
    stable_hash,
    stop_id,
)
from app.services.embedding_service import EmbeddingService

FIXTURE = Path(__file__).parents[1] / "fixtures" / "policeuk"


def rows(name: str) -> list[dict[str, str]]:
    with (FIXTURE / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_graph():
    return build_policeuk_graph(
        rows("crimes.csv"),
        rows("outcomes.csv"),
        rows("stops.csv"),
        parse_population_rows(rows("population.csv")),
        json.loads((FIXTURE / "force.json").read_text()),
        json.loads((FIXTURE / "neighbourhoods.json").read_text()),
        {key: [tuple(point) for point in polygon] for key, polygon in json.loads(
            (FIXTURE / "boundaries.json").read_text()
        ).items()},
        {"crime": "fixture-crimes.csv", "outcome": "fixture-outcomes.csv", "stop": "fixture-stops.csv"},
        "2026-01-01T00:00:00+00:00",
    )


def test_force_and_lsoa_normalization() -> None:
    assert normalize_force("Thames Valley Police") == "thames-valley"
    assert normalize_lsoa(" e01000001 ") == "E01000001"
    with pytest.raises(ValueError):
        normalize_lsoa("Oxford 1")


def test_deterministic_ids_and_duplicate_handling() -> None:
    crime = rows("crimes.csv")[0]
    assert crime_id(crime) == crime_id(dict(crime))
    assert stop_id(rows("stops.csv")[0], "thames-valley") == stop_id(
        rows("stops.csv")[0], "thames-valley"
    )
    assert stable_hash("a", "b") == stable_hash("a", "b")
    graph, documents, stats = build_policeuk_graph(
        [crime, dict(crime)], [], [], [], {"id": "thames-valley", "name": "Thames Valley Police"},
        [], {}, retrieved_at="2026-01-01T00:00:00+00:00",
    )
    assert stats.crimes == 1
    assert stats.duplicate_rows == 1
    assert len({document["id"] for document in documents}) == len(documents)
    assert len(graph) > 0


def test_archive_selection_inspects_members() -> None:
    names = [
        "2025-01/2025-01-thames-valley-street.csv",
        "2025-01/2025-01-thames-valley-outcomes.csv",
        "2025-01/2025-01-metropolitan-street.csv",
        "README.txt",
    ]
    assert select_archive_members(
        names, "thames-valley", ["2025-01"], {"crime", "outcome"}
    ) == sorted(names[:2])


def test_rows_are_limited_to_selected_event_months() -> None:
    assert filter_rows_to_months(
        [{"Month": "2026-05"}, {"Month": "2026-06"}], "crime", ["2026-06"]
    ) == [{"Month": "2026-06"}]
    assert filter_rows_to_months(
        [
            {"Date": "2026-05-31T23:30:00+00:00"},
            {"Date": "2026-06-01T00:30:00+00:00"},
        ],
        "stop",
        ["2026-06"],
    ) == [{"Date": "2026-06-01T00:30:00+00:00"}]


def test_population_exact_code_and_rate_generation() -> None:
    populations = parse_population_rows(rows("population.csv"))
    assert populations[0]["population"] == 2000
    graph, documents, stats = fixture_graph()
    rate = URIRef(f"{DATA}crime-rate/E01000001/2025-01/vehicle-crime")
    assert float(graph.value(rate, PUK.ratePerThousand)) == 1.0
    assert int(graph.value(rate, PUK.population)) == 2000
    assert stats.missing_population_joins == 0
    assert any(document["entity_type"] == "CrimeAggregate" and "per 1,000" in document["text"] for document in documents)


def test_exact_outcome_join_and_graph_paths() -> None:
    graph, _, stats = fixture_graph()
    crime = URIRef(f"{DATA}crime/crime-001")
    outcomes = list(graph.objects(crime, PUK.hasOutcome))
    assert len(outcomes) == 1
    assert graph.value(outcomes[0], PUK.belongsToCrime) == crime
    assert graph.value(outcomes[0], PUK.outcomeCategory) is not None
    assert stats.unmatched_outcomes == 1
    lsoa = graph.value(crime, PUK.locatedIn)
    assert lsoa == URIRef(f"{DATA}lsoa/E01000001")
    assert graph.value(lsoa, PUK.hasPopulationObservation) is not None


def test_spatial_assignment_and_derived_provenance() -> None:
    polygon = [(-1.30, 51.70), (-1.20, 51.70), (-1.20, 51.80), (-1.30, 51.80)]
    assert point_in_polygon(-1.25, 51.75, polygon)
    assert not point_in_polygon(-1.10, 51.75, polygon)
    assert assign_neighbourhood(-1.25, 51.75, {"N1": polygon}) == "N1"
    graph, _, _ = fixture_graph()
    street = graph.value(URIRef(f"{DATA}crime/crime-001"), PUK.occurredAt)
    assert graph.value(street, PUK.withinNeighbourhood) == URIRef(
        f"{DATA}neighbourhood/thames-valley/N1"
    )
    derivations = [
        subject for subject in graph.subjects(PUK.derivationMethod)
        if "point-in-polygon" in str(graph.value(subject, PUK.derivationMethod))
    ]
    assert derivations
    assert all(bool(graph.value(subject, PUK.isDerived)) for subject in derivations)


def test_stop_search_path_and_person_demographics_excluded() -> None:
    graph, _, stats = fixture_graph()
    event = next(graph.subjects(RDF.type, PUK.StopSearchEvent))
    street = graph.value(event, PUK.occurredAt)
    neighbourhood = graph.value(street, PUK.withinNeighbourhood)
    force = graph.value(neighbourhood, PUK.partOf)
    assert force == URIRef(f"{DATA}police-force/thames-valley")
    assert stats.stops == 2
    serialized = graph.serialize(format="turtle")
    assert "ethnicity" not in serialized.lower()
    assert "gender" not in serialized.lower()


def test_rdf_and_milvus_documents_have_provenance_and_mapping() -> None:
    graph, documents, stats = fixture_graph()
    assert stats.rdf_triples == len(graph)
    assert stats.milvus_documents == len(documents)
    assert documents
    for document in documents:
        assert document["metadata"]["source"]
        assert document["metadata"]["graph_uri"] == document["entity_uri"]
        assert (URIRef(document["entity_uri"]), None, None) in graph
    assert any("جرائم المركبات" in document["text"] for document in documents)


def test_e5_passage_formatting_is_applied_once() -> None:
    service = EmbeddingService(Settings.model_construct(embedding_model="intfloat/multilingual-e5-large"))
    graph, documents, _ = fixture_graph()
    del graph
    assert not documents[0]["text"].startswith("passage:")
    assert service._prefix("passage", documents[0]["text"]).startswith("passage: ")


def test_fixture_transform_is_idempotent() -> None:
    graph_one, documents_one, _ = fixture_graph()
    graph_two, documents_two, _ = fixture_graph()
    assert set(graph_one) == set(graph_two)
    assert documents_one == documents_two


def test_persisted_documents_stream_in_bounded_batches(tmp_path: Path) -> None:
    path = tmp_path / "evidence-documents.jsonl"
    path.write_text(
        "\n".join(
            json.dumps({"id": str(index), "text": f"document {index}"})
            for index in range(5)
        ),
        encoding="utf-8",
    )
    batches = list(_document_batches(path, 2))
    assert [len(batch) for batch in batches] == [2, 2, 1]
    assert [row["id"] for batch in batches for row in batch] == [
        "0",
        "1",
        "2",
        "3",
        "4",
    ]
