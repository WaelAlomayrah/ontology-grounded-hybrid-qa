"""Deterministic Police.uk + ONS ingestion using the existing RDF/vector pipeline.

The module deliberately excludes person-level stop/search demographics. Published
coordinates are approximate anonymised locations and spatial links are marked derived.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
import time
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote
from zipfile import ZipFile

import httpx
import pandas as pd
from rdflib import OWL, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef

from app.config import Settings

logger = logging.getLogger(__name__)

PUK = Namespace("https://w3id.org/ontology-qa/policeuk/")
DATA = Namespace("https://w3id.org/ontology-qa/resource/")
PROV = Namespace("http://www.w3.org/ns/prov#")
GEO = Namespace("http://www.opengis.net/ont/geosparql#")
OGL = "Open Government Licence v3.0"
POLICE_SOURCE = "Police.uk"
ONS_SOURCE = "Office for National Statistics"

CATEGORY_AR = {
    "anti-social-behaviour": "السلوك المعادي للمجتمع",
    "bicycle-theft": "سرقة الدراجات",
    "burglary": "السطو",
    "criminal-damage-arson": "أضرار جنائية وحرق متعمد",
    "drugs": "جرائم المخدرات",
    "other-crime": "جرائم أخرى",
    "other-theft": "سرقات أخرى",
    "possession-of-weapons": "حيازة أسلحة",
    "public-order": "النظام العام",
    "robbery": "السرقة بالإكراه",
    "shoplifting": "السرقة من المتاجر",
    "theft-from-the-person": "السرقة من الأشخاص",
    "vehicle-crime": "جرائم المركبات",
    "violent-crime": "جرائم العنف",
}

OUTCOME_AR = {
    "under-investigation": "قيد التحقيق",
    "investigation-complete-no-suspect-identified": "اكتمل التحقيق ولم يُحدد مشتبه به",
    "unable-to-prosecute-suspect": "تعذر ملاحقة المشتبه به قضائياً",
    "offender-given-a-caution": "تم تحذير الجاني",
    "offender-charged": "تم توجيه اتهام للجاني",
    "community-resolution": "تسوية مجتمعية",
    "a-no-further-action-disposal": "لا إجراء إضافي",
}

SEARCH_OBJECT_AR = {
    "controlled-drugs": "مخدرات خاضعة للرقابة",
    "offensive-weapons": "أسلحة هجومية",
    "stolen-goods": "بضائع مسروقة",
}

CLASS_LABELS = {
    "PoliceForce": ("Police Force", "جهة الشرطة"),
    "Neighbourhood": ("Neighbourhood", "منطقة"),
    "LSOA": ("Lower Layer Super Output Area", "منطقة إحصائية"),
    "StreetLocation": ("Street Location", "موقع شارع"),
    "CrimeIncident": ("Crime Incident", "واقعة جريمة"),
    "CrimeCategory": ("Crime Category", "فئة الجريمة"),
    "OutcomeEvent": ("Outcome Event", "حدث نتيجة"),
    "OutcomeCategory": ("Outcome Category", "فئة النتيجة"),
    "StopSearchEvent": ("Stop and Search Event", "حدث إيقاف وتفتيش"),
    "StopSearchOutcome": ("Stop and Search Outcome", "نتيجة الإيقاف والتفتيش"),
    "SearchObject": ("Search Object", "غرض التفتيش"),
    "Legislation": ("Legislation", "التشريع"),
    "PopulationObservation": ("Population Observation", "رصد عدد السكان"),
    "CrimeAggregate": ("Crime Aggregate", "إجمالي الجرائم"),
    "OutcomeAggregate": ("Outcome Aggregate", "إجمالي النتائج"),
    "StopSearchAggregate": ("Stop and Search Aggregate", "إجمالي الإيقاف والتفتيش"),
    "CrimeRateObservation": ("Crime Rate Observation", "معدل الجرائم"),
    "TimePeriod": ("Time Period", "فترة زمنية"),
    "Boundary": ("Boundary", "حدود جغرافية"),
}

PROPERTIES = {
    "reportedBy": "reported by",
    "fallsWithin": "falls within",
    "occurredAt": "occurred at",
    "locatedIn": "located in",
    "classifiedAs": "classified as",
    "hasOutcome": "has outcome",
    "belongsToCrime": "belongs to crime",
    "outcomeCategory": "outcome category",
    "occurredDuring": "occurred during",
    "hasNeighbourhood": "has neighbourhood",
    "hasBoundary": "has boundary",
    "withinNeighbourhood": "within neighbourhood",
    "withinLSOA": "within LSOA",
    "conductedBy": "conducted by",
    "searchedFor": "searched for",
    "authorizedBy": "authorised by",
    "hasPopulationObservation": "has population observation",
    "partOf": "part of",
    "describesArea": "describes area",
    "describesCategory": "describes category",
}


def stable_hash(*values: object, length: int = 64) -> str:
    canonical = "\x1f".join("" if value is None else str(value).strip() for value in values)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:length]


def normalize_force(value: str) -> str:
    text = value.strip().lower().replace("&", "and")
    text = re.sub(r"\b(constabulary|police|service)\b", "", text)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def normalize_lsoa(value: object) -> str:
    code = re.sub(r"\s+", "", str(value or "")).upper()
    if not code:
        return ""
    if not re.fullmatch(r"[EWN]\d{8}", code):
        raise ValueError(f"Invalid 2021 LSOA code: {value!r}")
    return code


def normalize_slug(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-") or "unknown"


def parse_float(value: object) -> float | None:
    try:
        return float(str(value).strip()) if str(value).strip() else None
    except (TypeError, ValueError):
        return None


def point_in_polygon(longitude: float, latitude: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon; polygon tuples are (longitude, latitude)."""
    inside = False
    if len(polygon) < 3:
        return False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        intersects = (y1 > latitude) != (y2 > latitude) and longitude < (
            (x2 - x1) * (latitude - y1) / (y2 - y1 or 1e-15) + x1
        )
        if intersects:
            inside = not inside
        previous = current
    return inside


@dataclass
class PoliceUKStats:
    files_downloaded: int = 0
    rows_parsed: int = 0
    crimes: int = 0
    outcomes: int = 0
    stops: int = 0
    forces: int = 0
    neighbourhoods: int = 0
    lsoas: int = 0
    population_observations: int = 0
    aggregates: int = 0
    rdf_entities: int = 0
    rdf_triples: int = 0
    milvus_documents: int = 0
    embedded_passages: int = 0
    skipped_rows: int = 0
    duplicate_rows: int = 0
    missing_lsoa: int = 0
    unmatched_outcomes: int = 0
    unmapped_neighbourhood_points: int = 0
    missing_population_joins: int = 0
    unknown_categories: list[str] = field(default_factory=list)
    api_failures: list[str] = field(default_factory=list)
    selected_files: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return vars(self)


class CachedPoliceUKClient:
    def __init__(self, raw_dir: Path, timeout: float, retries: int, user_agent: str) -> None:
        self.cache_dir = raw_dir / "api-cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.retries = retries
        self.user_agent = user_agent

    def get_json(self, url: str, offline: bool = False) -> Any:
        cache = self.cache_dir / f"{stable_hash(url)}.json"
        if cache.is_file():
            return json.loads(cache.read_text(encoding="utf-8"))
        if offline:
            raise FileNotFoundError(f"Offline API cache miss: {url}")
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with httpx.Client(
                    timeout=self.timeout,
                    headers={"User-Agent": self.user_agent, "Accept": "application/json"},
                    follow_redirects=True,
                ) as client:
                    response = client.get(url)
                    response.raise_for_status()
                    payload = response.json()
                    cache.write_bytes(response.content)
                    return payload
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(min(2**attempt, 8))
        raise RuntimeError(f"Police.uk request failed: {url}: {last_error}")


def latest_complete_months(client: CachedPoliceUKClient, count: int, offline: bool) -> list[str]:
    rows = client.get_json("https://data.police.uk/api/crimes-street-dates", offline)
    months = sorted(
        {str(row.get("date", "")) for row in rows if re.fullmatch(r"\d{4}-\d{2}", str(row.get("date", "")))}
    )
    if len(months) < count:
        raise ValueError(f"Only {len(months)} Police.uk months are available; requested {count}")
    return months[-count:]


def download_file(url: str, destination: Path, timeout: float, user_agent: str) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    digest = hashlib.sha256()
    with httpx.stream(
        "GET",
        url,
        timeout=httpx.Timeout(timeout, read=max(timeout, 600)),
        headers={"User-Agent": user_agent},
        follow_redirects=True,
    ) as response:
        response.raise_for_status()
        with temporary.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
                digest.update(chunk)
    temporary.replace(destination)
    return digest.hexdigest()


def archive_member_kind(name: str) -> str | None:
    lowered = Path(name).name.lower()
    if lowered.endswith("-street.csv"):
        return "crime"
    if lowered.endswith("-outcomes.csv"):
        return "outcome"
    if lowered.endswith("-stop-and-search.csv"):
        return "stop"
    return None


def select_archive_members(
    names: Iterable[str], force_id: str, months: Iterable[str], includes: set[str]
) -> list[str]:
    wanted_months = set(months)
    selected = []
    force_marker = f"-{force_id}-"
    for name in names:
        basename = Path(name).name.lower()
        match = re.match(r"^(\d{4}-\d{2})-", basename)
        kind = archive_member_kind(name)
        if match and match.group(1) in wanted_months and force_marker in basename and kind in includes:
            selected.append(name)
    return sorted(selected)


def filter_rows_to_months(
    rows: Iterable[dict[str, Any]], kind: str, months: Iterable[str]
) -> list[dict[str, Any]]:
    """Keep records whose published event month is explicitly selected."""
    allowed = set(months)
    field = "Date" if kind == "stop" else "Month"
    return [
        row
        for row in rows
        if str(row.get(field) or "").strip()[:7] in allowed
    ]


def read_csv_rows(raw: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))


def crime_id(row: dict[str, Any]) -> str:
    persistent = str(row.get("Crime ID") or row.get("persistent_id") or "").strip()
    if persistent:
        return persistent
    return stable_hash(
        row.get("Month"),
        row.get("Reported by"),
        row.get("Longitude"),
        row.get("Latitude"),
        row.get("Location"),
        row.get("LSOA code"),
        row.get("Crime type"),
        row.get("Context"),
    )


def stop_id(row: dict[str, Any], force_id: str) -> str:
    return stable_hash(
        force_id,
        row.get("Date"),
        row.get("Longitude"),
        row.get("Latitude"),
        row.get("Type"),
        row.get("Object of search"),
        row.get("Legislation"),
        row.get("Outcome"),
        row.get("Operation name"),
    )


def parse_population_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        lowered = {str(key).strip().lower(): value for key, value in row.items()}
        raw_code = next(
            (str(value).strip().upper() for key, value in lowered.items()
             if ("lsoa" in key and "code" in key) or key in {"geography code", "geography_code"}),
            "",
        )
        code = normalize_lsoa(raw_code) if re.fullmatch(r"[EWN]\d{8}", re.sub(r"\s+", "", raw_code)) else ""
        if not code:
            continue
        name = next(
            (
                str(value).strip()
                for key, value in lowered.items()
                if ("lsoa" in key and "name" in key) or key in {"geography", "geography name"}
            ),
            "",
        )
        population_value = next(
            (
                value
                for key, value in lowered.items()
                if key in {"population", "total population", "value", "observation", "obs_value"}
            ),
            None,
        )
        population = parse_float(population_value)
        if population is None or population <= 0:
            continue
        year_text = next(
            (
                str(value)
                for key, value in lowered.items()
                if key in {"year", "time", "time_name", "date", "date_name", "reference_year"}
            ),
            "",
        )
        year_match = re.search(r"20\d{2}", year_text)
        year = int(year_match.group()) if year_match else 2024
        # Long-form ONS downloads may include age/sex dimensions; retain totals only.
        age = str(lowered.get("age", "Total")).lower()
        sex = str(lowered.get("sex", "All")).lower()
        if age not in {"", "total", "all ages"} or sex not in {"", "all", "persons"}:
            continue
        result[code] = {
            "lsoa_code": code,
            "lsoa_name": name,
            "population": int(population),
            "reference_year": year,
            "source": ONS_SOURCE,
        }
    return sorted(result.values(), key=lambda item: item["lsoa_code"])


def load_population_file(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return parse_population_rows(csv.DictReader(handle))
    if path.suffix.lower() not in {".xlsx", ".xls"}:
        raise ValueError(f"Unsupported ONS population format: {path.suffix}")
    candidates: list[dict[str, Any]] = []
    workbook = pd.ExcelFile(path)
    for sheet in workbook.sheet_names:
        preview = pd.read_excel(path, sheet_name=sheet, header=None, nrows=20)
        header_index = next(
            (
                int(index)
                for index, row in preview.iterrows()
                if any("lsoa" in str(value).lower() and "code" in str(value).lower() for value in row)
            ),
            None,
        )
        if header_index is None:
            continue
        frame = pd.read_excel(path, sheet_name=sheet, header=header_index)
        candidates.extend(frame.where(pd.notna(frame), None).to_dict(orient="records"))
    parsed = parse_population_rows(candidates)
    if not parsed:
        raise ValueError("No 2021 LSOA total-population rows found in the official ONS workbook")
    return parsed


def download_ons_population(
    base_url: str,
    lsoa_codes: Iterable[str],
    raw_dir: Path,
    timeout: float,
    retries: int,
    user_agent: str,
    chunk_size: int = 500,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Download official ONS Nomis totals for exact 2021 LSOA codes."""
    codes = sorted({normalize_lsoa(code) for code in lsoa_codes if code})
    if not codes:
        return [], []
    population_rows: list[dict[str, Any]] = []
    files: list[str] = []
    for offset in range(0, len(codes), chunk_size):
        chunk = codes[offset : offset + chunk_size]
        params = {
            "geography": ",".join(chunk),
            "time": "latest",
            "gender": "0",
            "c_age": "0",
            "measures": "20100",
            "select": "geography_code,geography_name,date_name,obs_value",
        }
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                with httpx.Client(
                    timeout=timeout,
                    headers={"User-Agent": user_agent, "Accept": "text/csv"},
                    follow_redirects=True,
                ) as client:
                    response = client.get(base_url, params=params)
                    response.raise_for_status()
                    name = f"ons-population-{offset // chunk_size + 1:04d}.csv"
                    path = raw_dir / name
                    path.write_bytes(response.content)
                    files.append(name)
                    population_rows.extend(
                        parse_population_rows(
                            csv.DictReader(io.StringIO(response.content.decode("utf-8-sig")))
                        )
                    )
                    break
            except (httpx.HTTPError, UnicodeError, ValueError) as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(min(2**attempt, 8))
        else:
            raise RuntimeError(f"ONS Nomis population request failed: {last_error}")
    by_code = {row["lsoa_code"]: row for row in population_rows}
    missing = sorted(set(codes) - set(by_code))
    if missing:
        logger.warning(
            "ons_population_codes_missing",
            extra={"event": "ons_population_codes_missing", "missing_count": len(missing)},
        )
    return sorted(by_code.values(), key=lambda row: row["lsoa_code"]), files


def _add_schema(graph: Graph) -> None:
    graph.bind("policeuk", PUK)
    graph.bind("prov", PROV)
    graph.bind("geo", GEO)
    ontology = PUK.Ontology
    graph.add((ontology, RDF.type, OWL.Ontology))
    graph.add((ontology, RDFS.label, Literal("Public-safety extension ontology", lang="en")))
    for name, labels in CLASS_LABELS.items():
        uri = PUK[name]
        graph.add((uri, RDF.type, OWL.Class))
        graph.add((uri, RDFS.label, Literal(labels[0], lang="en")))
        graph.add((uri, RDFS.label, Literal(labels[1], lang="ar")))
    for name, label in PROPERTIES.items():
        uri = PUK[name]
        graph.add((uri, RDF.type, OWL.ObjectProperty))
        graph.add((uri, RDFS.label, Literal(label, lang="en")))
    for name in (
        "sourceDataset", "sourceRecordId", "sourceFile", "sourceRetrievedAt",
        "sourceLicence", "isDerived", "derivationMethod", "month", "latitude",
        "longitude", "incidentCount", "population", "populationReferenceYear",
        "ratePerThousand", "calculationMethod",
    ):
        graph.add((PUK[name], RDF.type, OWL.DatatypeProperty))
        graph.add((PUK[name], RDFS.label, Literal(re.sub(r"(?<!^)([A-Z])", r" \1", name).lower())))


def _provenance(
    graph: Graph,
    subject: URIRef,
    source: str,
    record_id: str,
    source_file: str,
    retrieved_at: str,
    derived: bool = False,
    method: str = "",
) -> None:
    graph.add((subject, PUK.sourceDataset, Literal(source)))
    graph.add((subject, PUK.sourceRecordId, Literal(record_id)))
    graph.add((subject, PUK.sourceFile, Literal(source_file)))
    graph.add((subject, PUK.sourceRetrievedAt, Literal(retrieved_at, datatype=XSD.dateTime)))
    graph.add((subject, PUK.sourceLicence, Literal(OGL)))
    graph.add((subject, PUK.isDerived, Literal(derived, datatype=XSD.boolean)))
    if method:
        graph.add((subject, PUK.derivationMethod, Literal(method)))


def _uri(kind: str, *parts: object) -> URIRef:
    path = "/".join(quote(str(part).strip(), safe="-._~") for part in parts)
    return URIRef(f"{DATA}{kind}/{path}")


def _add_entity(graph: Graph, uri: URIRef, class_name: str, label: str) -> None:
    graph.add((uri, RDF.type, PUK[class_name]))
    graph.add((uri, RDFS.label, Literal(label)))


def _month_uri(graph: Graph, month: str) -> URIRef:
    uri = _uri("time-period", month)
    _add_entity(graph, uri, "TimePeriod", month)
    graph.set((uri, PUK.month, Literal(month, datatype=XSD.gYearMonth)))
    return uri


def _category_uri(graph: Graph, category: str) -> URIRef:
    slug = normalize_slug(category)
    uri = _uri("crime-category", slug)
    _add_entity(graph, uri, "CrimeCategory", category or "Unknown crime category")
    if slug in CATEGORY_AR:
        graph.add((uri, RDFS.label, Literal(CATEGORY_AR[slug], lang="ar")))
    return uri


def assign_neighbourhood(
    longitude: float | None,
    latitude: float | None,
    boundaries: dict[str, list[tuple[float, float]]],
) -> str | None:
    if longitude is None or latitude is None:
        return None
    matches = [
        neighbourhood_id
        for neighbourhood_id, polygon in boundaries.items()
        if point_in_polygon(longitude, latitude, polygon)
    ]
    return matches[0] if len(matches) == 1 else None


def _document(
    record_type: str,
    entity_uri: URIRef,
    label: str,
    text: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": stable_hash("policeuk", record_type, entity_uri, length=32),
        "entity_uri": str(entity_uri),
        "entity_type": record_type,
        "label": label,
        "text": text,
        "source": "policeuk",
        "metadata": {
            "source": POLICE_SOURCE,
            "source_type": metadata.get("source_type", "open-data"),
            "record_type": record_type,
            "entity_id": str(entity_uri),
            "entity_type": record_type,
            "graph_uri": str(entity_uri),
            "language": "en",
            "derived": bool(metadata.get("derived", False)),
            **metadata,
        },
    }


def build_policeuk_graph(
    crimes: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    stops: list[dict[str, Any]],
    populations: list[dict[str, Any]],
    force: dict[str, Any],
    neighbourhoods: list[dict[str, Any]],
    boundaries: dict[str, list[tuple[float, float]]],
    source_files: dict[str, str] | None = None,
    retrieved_at: str | None = None,
) -> tuple[Graph, list[dict[str, Any]], PoliceUKStats]:
    started = time.perf_counter()
    source_files = source_files or {}
    retrieved_at = retrieved_at or datetime.now(UTC).isoformat()
    graph, stats = Graph(), PoliceUKStats()
    _add_schema(graph)
    force_id = str(force["id"])
    force_uri = _uri("police-force", force_id)
    force_name = str(force.get("name") or force_id)
    _add_entity(graph, force_uri, "PoliceForce", force_name)
    _provenance(graph, force_uri, POLICE_SOURCE, force_id, source_files.get("force", "api/forces"), retrieved_at)
    stats.forces = 1

    for item in neighbourhoods:
        identifier = str(item["id"])
        neighbourhood_uri = _uri("neighbourhood", force_id, identifier)
        _add_entity(graph, neighbourhood_uri, "Neighbourhood", str(item.get("name") or identifier))
        graph.add((force_uri, PUK.hasNeighbourhood, neighbourhood_uri))
        graph.add((neighbourhood_uri, PUK.partOf, force_uri))
        _provenance(
            graph, neighbourhood_uri, POLICE_SOURCE, identifier,
            source_files.get("neighbourhoods", f"api/{force_id}/neighbourhoods"), retrieved_at,
        )
        if identifier in boundaries:
            boundary_uri = _uri("boundary", force_id, identifier)
            _add_entity(graph, boundary_uri, "Boundary", f"{item.get('name', identifier)} boundary")
            coordinates = ", ".join(f"{lon} {lat}" for lon, lat in boundaries[identifier])
            graph.add((boundary_uri, GEO.asWKT, Literal(f"POLYGON (({coordinates}))", datatype=GEO.wktLiteral)))
            graph.add((neighbourhood_uri, PUK.hasBoundary, boundary_uri))
            _provenance(
                graph, boundary_uri, POLICE_SOURCE, identifier,
                source_files.get("boundaries", f"api/{force_id}/{identifier}/boundary"), retrieved_at,
            )
    stats.neighbourhoods = len(neighbourhoods)

    population_by_lsoa = {row["lsoa_code"]: row for row in populations}
    lsoa_names: dict[str, str] = {}
    for row in populations:
        code = normalize_lsoa(row["lsoa_code"])
        lsoa_uri = _uri("lsoa", code)
        lsoa_names[code] = str(row.get("lsoa_name") or code)
        _add_entity(graph, lsoa_uri, "LSOA", lsoa_names[code])
        population_uri = _uri("population", code, row["reference_year"])
        _add_entity(graph, population_uri, "PopulationObservation", f"{code} population {row['reference_year']}")
        graph.add((lsoa_uri, PUK.hasPopulationObservation, population_uri))
        graph.add((population_uri, PUK.describesArea, lsoa_uri))
        graph.add((population_uri, PUK.population, Literal(int(row["population"]), datatype=XSD.integer)))
        graph.add((population_uri, PUK.populationReferenceYear, Literal(int(row["reference_year"]), datatype=XSD.gYear)))
        _provenance(
            graph, population_uri, ONS_SOURCE, f"{code}/{row['reference_year']}",
            source_files.get("population", "ons-population.csv"), retrieved_at,
        )
    stats.population_observations = len(populations)

    documents: list[dict[str, Any]] = []
    seen_crimes: set[str] = set()
    crime_context: dict[str, tuple[URIRef, str, str, str]] = {}
    crime_counts: Counter[tuple[str, str, str]] = Counter()
    outcome_counts: Counter[tuple[str, str, str, str]] = Counter()
    stop_counts: Counter[tuple[str, str, str, str]] = Counter()
    unknown_categories: set[str] = set()

    for row in crimes:
        stats.rows_parsed += 1
        identifier = crime_id(row)
        if identifier in seen_crimes:
            stats.duplicate_rows += 1
            continue
        seen_crimes.add(identifier)
        month = str(row.get("Month") or row.get("month") or "")
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            stats.skipped_rows += 1
            continue
        category = str(row.get("Crime type") or row.get("category") or "Unknown").strip()
        category_slug = normalize_slug(category)
        if category_slug not in CATEGORY_AR:
            unknown_categories.add(category)
        lsoa_code = normalize_lsoa(row.get("LSOA code") or "") if row.get("LSOA code") else ""
        if not lsoa_code:
            stats.missing_lsoa += 1
        else:
            lsoa_names.setdefault(lsoa_code, str(row.get("LSOA name") or lsoa_code))
        crime_uri = _uri("crime", identifier)
        _add_entity(graph, crime_uri, "CrimeIncident", f"{category} incident {identifier[:12]}")
        graph.add((crime_uri, PUK.reportedBy, force_uri))
        graph.add((crime_uri, PUK.fallsWithin, force_uri))
        category_uri = _category_uri(graph, category)
        graph.add((crime_uri, PUK.classifiedAs, category_uri))
        graph.add((crime_uri, PUK.occurredDuring, _month_uri(graph, month)))
        longitude, latitude = parse_float(row.get("Longitude")), parse_float(row.get("Latitude"))
        street_id = str(row.get("Location") or row.get("street_id") or stable_hash(longitude, latitude, length=16))
        street_uri = _uri("street-location", street_id)
        street_label = str(row.get("Location") or "Published anonymised location")
        _add_entity(graph, street_uri, "StreetLocation", street_label)
        graph.add((crime_uri, PUK.occurredAt, street_uri))
        if longitude is not None and latitude is not None:
            graph.set((street_uri, PUK.longitude, Literal(longitude, datatype=XSD.decimal)))
            graph.set((street_uri, PUK.latitude, Literal(latitude, datatype=XSD.decimal)))
        if lsoa_code:
            lsoa_uri = _uri("lsoa", lsoa_code)
            _add_entity(graph, lsoa_uri, "LSOA", lsoa_names[lsoa_code])
            graph.add((crime_uri, PUK.locatedIn, lsoa_uri))
            graph.add((street_uri, PUK.withinLSOA, lsoa_uri))
            crime_counts[(lsoa_code, month, category_slug)] += 1
        neighbourhood_id = assign_neighbourhood(longitude, latitude, boundaries)
        if neighbourhood_id:
            neighbourhood_uri = _uri("neighbourhood", force_id, neighbourhood_id)
            graph.add((street_uri, PUK.withinNeighbourhood, neighbourhood_uri))
            relation_uri = _uri("derivation", "street-neighbourhood", identifier)
            _add_entity(graph, relation_uri, "Boundary", f"Spatial assignment for {identifier[:12]}")
            _provenance(
                graph, relation_uri, POLICE_SOURCE, identifier, source_files.get("crime", ""),
                retrieved_at, True, "point-in-polygon using anonymised Police.uk point",
            )
        elif boundaries and longitude is not None and latitude is not None:
            stats.unmapped_neighbourhood_points += 1
        _provenance(
            graph, crime_uri, POLICE_SOURCE, identifier, source_files.get("crime", "Police.uk archive"),
            retrieved_at,
        )
        last_outcome = str(row.get("Last outcome category") or "").strip()
        passage = (
            f"Crime incident. Category: {category}"
            f"{f' ({CATEGORY_AR[category_slug]})' if category_slug in CATEGORY_AR else ''}. "
            f"Month: {month}. Area: {lsoa_names.get(lsoa_code, 'not published')}, "
            f"LSOA {lsoa_code or 'not published'}. Police force: {force_name}. "
            f"Approximate anonymised location: {street_label}. "
            f"Latest outcome: {last_outcome or 'not published'}. Source: Police.uk."
        )
        documents.append(_document("CrimeIncident", crime_uri, f"{category} {month}", passage, {
            "force_id": force_id, "force_name": force_name, "month": month,
            "lsoa_code": lsoa_code, "lsoa_name": lsoa_names.get(lsoa_code, ""),
            "crime_category": category_slug, "outcome_category": normalize_slug(last_outcome) if last_outcome else "",
            "source_record_id": identifier, "derived": False,
        }))
        crime_context[identifier] = (crime_uri, lsoa_code, month, category_slug)
        stats.crimes += 1

    seen_outcomes: set[str] = set()
    for row in outcomes:
        stats.rows_parsed += 1
        linked_id = str(row.get("Crime ID") or row.get("persistent_id") or "").strip()
        if not linked_id or linked_id not in crime_context:
            stats.unmatched_outcomes += 1
            continue
        outcome_month = str(row.get("Month") or row.get("date") or "")
        category = str(row.get("Outcome type") or row.get("category") or "Unknown outcome").strip()
        identifier = stable_hash(linked_id, outcome_month, category)
        if identifier in seen_outcomes:
            stats.duplicate_rows += 1
            continue
        seen_outcomes.add(identifier)
        outcome_uri = _uri("outcome", linked_id, outcome_month, normalize_slug(category))
        category_uri = _uri("outcome-category", normalize_slug(category))
        _add_entity(graph, outcome_uri, "OutcomeEvent", f"{category} {outcome_month}")
        _add_entity(graph, category_uri, "OutcomeCategory", category)
        if normalize_slug(category) in OUTCOME_AR:
            graph.add((category_uri, RDFS.label, Literal(OUTCOME_AR[normalize_slug(category)], lang="ar")))
        crime_uri, lsoa_code, crime_month, crime_category = crime_context[linked_id]
        graph.add((crime_uri, PUK.hasOutcome, outcome_uri))
        graph.add((outcome_uri, PUK.belongsToCrime, crime_uri))
        graph.add((outcome_uri, PUK.outcomeCategory, category_uri))
        graph.add((outcome_uri, PUK.occurredDuring, _month_uri(graph, outcome_month or crime_month)))
        _provenance(
            graph, outcome_uri, POLICE_SOURCE, identifier,
            source_files.get("outcome", "Police.uk archive"), retrieved_at,
            method="bulk exact Crime ID join",
        )
        if lsoa_code:
            outcome_counts[(lsoa_code, crime_month, crime_category, normalize_slug(category))] += 1
        stats.outcomes += 1

    seen_stops: set[str] = set()
    for row in stops:
        stats.rows_parsed += 1
        identifier = stop_id(row, force_id)
        if identifier in seen_stops:
            stats.duplicate_rows += 1
            continue
        seen_stops.add(identifier)
        date = str(row.get("Date") or "")
        month = date[:7]
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            stats.skipped_rows += 1
            continue
        longitude, latitude = parse_float(row.get("Longitude")), parse_float(row.get("Latitude"))
        object_name = str(row.get("Object of search") or "Not published").strip()
        outcome_name = str(row.get("Outcome") or "Not published").strip()
        legislation = str(row.get("Legislation") or "Not published").strip()
        event_uri = _uri("stop-search", identifier)
        _add_entity(graph, event_uri, "StopSearchEvent", f"Stop and search {identifier[:12]}")
        graph.add((event_uri, PUK.conductedBy, force_uri))
        graph.add((event_uri, PUK.occurredDuring, _month_uri(graph, month)))
        object_uri = _uri("search-object", normalize_slug(object_name))
        outcome_uri = _uri("stop-search-outcome", normalize_slug(outcome_name))
        legislation_uri = _uri("legislation", normalize_slug(legislation))
        _add_entity(graph, object_uri, "SearchObject", object_name)
        _add_entity(graph, outcome_uri, "StopSearchOutcome", outcome_name)
        _add_entity(graph, legislation_uri, "Legislation", legislation)
        if normalize_slug(object_name) in SEARCH_OBJECT_AR:
            graph.add((object_uri, RDFS.label, Literal(SEARCH_OBJECT_AR[normalize_slug(object_name)], lang="ar")))
        if normalize_slug(outcome_name) in OUTCOME_AR:
            graph.add((outcome_uri, RDFS.label, Literal(OUTCOME_AR[normalize_slug(outcome_name)], lang="ar")))
        graph.add((event_uri, PUK.searchedFor, object_uri))
        graph.add((event_uri, PUK.hasOutcome, outcome_uri))
        graph.add((event_uri, PUK.authorizedBy, legislation_uri))
        street_label = str(row.get("Location") or "Published anonymised location")
        street_uri = _uri("street-location", stable_hash(longitude, latitude, street_label, length=16))
        _add_entity(graph, street_uri, "StreetLocation", street_label)
        graph.add((event_uri, PUK.occurredAt, street_uri))
        neighbourhood_id = assign_neighbourhood(longitude, latitude, boundaries)
        if neighbourhood_id:
            neighbourhood_uri = _uri("neighbourhood", force_id, neighbourhood_id)
            graph.add((event_uri, PUK.withinNeighbourhood, neighbourhood_uri))
            graph.add((street_uri, PUK.withinNeighbourhood, neighbourhood_uri))
            stop_counts[(neighbourhood_id, month, normalize_slug(object_name), normalize_slug(outcome_name))] += 1
        elif boundaries and longitude is not None and latitude is not None:
            stats.unmapped_neighbourhood_points += 1
        _provenance(
            graph, event_uri, POLICE_SOURCE, identifier, source_files.get("stop", "Police.uk archive"),
            retrieved_at,
        )
        stats.stops += 1

    for (lsoa_code, month, category_slug), count in sorted(crime_counts.items()):
        aggregate_uri = _uri("crime-aggregate", lsoa_code, month, category_slug)
        _add_entity(graph, aggregate_uri, "CrimeAggregate", f"{lsoa_code} {month} {category_slug}: {count}")
        graph.add((aggregate_uri, PUK.describesArea, _uri("lsoa", lsoa_code)))
        graph.add((aggregate_uri, PUK.describesCategory, _uri("crime-category", category_slug)))
        graph.add((aggregate_uri, PUK.occurredDuring, _month_uri(graph, month)))
        graph.add((aggregate_uri, PUK.incidentCount, Literal(count, datatype=XSD.integer)))
        graph.add((aggregate_uri, PUK.reportedBy, force_uri))
        _provenance(
            graph, aggregate_uri, POLICE_SOURCE, f"{lsoa_code}/{month}/{category_slug}",
            source_files.get("crime", "Police.uk archive"), retrieved_at, True,
            "deterministic count grouped by LSOA, month, and crime category",
        )
        population = population_by_lsoa.get(lsoa_code)
        rate_text = ""
        if population:
            rate = count / int(population["population"]) * 1000
            rate_uri = _uri("crime-rate", lsoa_code, month, category_slug)
            _add_entity(graph, rate_uri, "CrimeRateObservation", f"{lsoa_code} {category_slug} rate {rate:.3f}")
            graph.add((rate_uri, PUK.describesArea, _uri("lsoa", lsoa_code)))
            graph.add((rate_uri, PUK.describesCategory, _uri("crime-category", category_slug)))
            graph.add((rate_uri, PUK.occurredDuring, _month_uri(graph, month)))
            graph.add((rate_uri, PUK.incidentCount, Literal(count, datatype=XSD.integer)))
            graph.add((rate_uri, PUK.population, Literal(int(population["population"]), datatype=XSD.integer)))
            graph.add((rate_uri, PUK.populationReferenceYear, Literal(int(population["reference_year"]), datatype=XSD.gYear)))
            graph.add((rate_uri, PUK.ratePerThousand, Literal(round(rate, 6), datatype=XSD.decimal)))
            graph.add((rate_uri, PUK.calculationMethod, Literal("incident count / ONS population * 1,000")))
            _provenance(
                graph, rate_uri, f"{POLICE_SOURCE}; {ONS_SOURCE}",
                f"{lsoa_code}/{month}/{category_slug}", "derived", retrieved_at, True,
                "Police.uk incident count divided by exact-code ONS LSOA population",
            )
            rate_text = (
                f" The area population used for normalization was {population['population']} residents "
                f"(ONS {population['reference_year']}). The descriptive crime rate was {rate:.2f} "
                "incidents per 1,000 residents."
            )
        else:
            stats.missing_population_joins += 1
        category_label = category_slug.replace("-", " ")
        passage = (
            f"In {month}, LSOA {lsoa_code} ({lsoa_names.get(lsoa_code, lsoa_code)}) recorded "
            f"{count} {category_label} incidents.{rate_text} Police force: {force_name}. "
            f"Sources: Police.uk{' and Office for National Statistics' if population else ''}."
        )
        documents.append(_document("CrimeAggregate", aggregate_uri, f"{lsoa_code} {category_label} {month}", passage, {
            "force_id": force_id, "force_name": force_name, "month": month,
            "lsoa_code": lsoa_code, "lsoa_name": lsoa_names.get(lsoa_code, ""),
            "crime_category": category_slug, "source_record_id": f"{lsoa_code}/{month}/{category_slug}",
            "derived": True,
        }))
        stats.aggregates += 1

    for key, count in sorted(outcome_counts.items()):
        lsoa_code, month, crime_category, outcome_category = key
        uri = _uri("outcome-aggregate", *key)
        _add_entity(graph, uri, "OutcomeAggregate", f"{lsoa_code} {month} {outcome_category}: {count}")
        graph.add((uri, PUK.describesArea, _uri("lsoa", lsoa_code)))
        graph.add((uri, PUK.incidentCount, Literal(count, datatype=XSD.integer)))
        _provenance(graph, uri, POLICE_SOURCE, "/".join(key), source_files.get("outcome", ""), retrieved_at, True, "exact-linked outcome count")
        documents.append(_document("OutcomeAggregate", uri, str(graph.value(uri, RDFS.label)), (
            f"In LSOA {lsoa_code} during {month}, {crime_category.replace('-', ' ')} incidents "
            f"had {count} recorded outcomes in category {outcome_category.replace('-', ' ')}. Source: Police.uk."
        ), {"force_id": force_id, "force_name": force_name, "month": month, "lsoa_code": lsoa_code,
             "crime_category": crime_category, "outcome_category": outcome_category, "derived": True,
             "source_record_id": "/".join(key)}))
        stats.aggregates += 1

    for key, count in sorted(stop_counts.items()):
        neighbourhood_id, month, search_object, outcome = key
        uri = _uri("stop-search-aggregate", *key)
        _add_entity(graph, uri, "StopSearchAggregate", f"{neighbourhood_id} {month} {search_object}: {count}")
        graph.add((uri, PUK.incidentCount, Literal(count, datatype=XSD.integer)))
        graph.add((uri, PUK.withinNeighbourhood, _uri("neighbourhood", force_id, neighbourhood_id)))
        _provenance(graph, uri, POLICE_SOURCE, "/".join(key), source_files.get("stop", ""), retrieved_at, True, "published stop/search count")
        documents.append(_document("StopSearchAggregate", uri, str(graph.value(uri, RDFS.label)), (
            f"During {month} in neighbourhood {neighbourhood_id}, {count} published stop and search "
            f"events recorded object {search_object.replace('-', ' ')} and outcome {outcome.replace('-', ' ')}. "
            "Source: Police.uk."
        ), {"force_id": force_id, "force_name": force_name, "month": month,
             "neighbourhood_id": neighbourhood_id, "outcome_category": outcome,
             "derived": True, "source_record_id": "/".join(key)}))
        stats.aggregates += 1

    for code, population in sorted(population_by_lsoa.items()):
        lsoa_uri = _uri("lsoa", code)
        documents.append(_document("LSOA", lsoa_uri, str(population.get("lsoa_name") or code), (
            f"{code} is a 2021 Lower Layer Super Output Area named "
            f"{population.get('lsoa_name') or code}. Population: {population['population']} "
            f"residents in {population['reference_year']}. Source: Office for National Statistics."
        ), {"lsoa_code": code, "lsoa_name": population.get("lsoa_name", ""),
             "source_type": "official-statistics", "source_record_id": f"{code}/{population['reference_year']}",
             "derived": False}))

    stats.unknown_categories = sorted(unknown_categories)
    stats.lsoas = len({str(subject) for subject in graph.subjects(RDF.type, PUK.LSOA)})
    stats.rdf_entities = len({subject for subject in graph.subjects(RDF.type)})
    stats.rdf_triples = len(graph)
    ids = [document["id"] for document in documents]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate deterministic Milvus document IDs")
    for document in documents:
        metadata = document["metadata"]
        if not metadata.get("source") or not metadata.get("graph_uri"):
            raise ValueError("Every Police.uk vector document requires provenance and graph_uri")
        if (URIRef(str(metadata["graph_uri"])), None, None) not in graph:
            raise ValueError(f"Vector graph URI does not exist: {metadata['graph_uri']}")
    stats.milvus_documents = len(documents)
    stats.embedded_passages = len(documents)
    stats.timings["transform_seconds"] = round(time.perf_counter() - started, 3)
    return graph, documents, stats


def _load_boundaries(raw_dir: Path) -> tuple[list[dict[str, Any]], dict[str, list[tuple[float, float]]]]:
    neighbourhood_path = raw_dir / "neighbourhoods.json"
    neighbourhoods = json.loads(neighbourhood_path.read_text(encoding="utf-8")) if neighbourhood_path.is_file() else []
    boundaries: dict[str, list[tuple[float, float]]] = {}
    boundary_dir = raw_dir / "boundaries"
    for path in boundary_dir.glob("*.json") if boundary_dir.is_dir() else []:
        rows = json.loads(path.read_text(encoding="utf-8"))
        polygon = [
            (float(row["longitude"]), float(row["latitude"]))
            for row in rows
            if row.get("longitude") is not None and row.get("latitude") is not None
        ]
        if len(polygon) >= 3:
            boundaries[path.stem] = polygon
    return neighbourhoods, boundaries


def _write_processed(directory: Path, name: str, rows: list[dict[str, Any]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    columns = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_report(root: Path, stats: PoliceUKStats, manifest: dict[str, Any]) -> None:
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    payload = {"dataset": "policeuk", "manifest": manifest, **stats.as_dict()}
    (reports / "latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Police.uk ingestion report", ""]
    lines.extend(f"- **{key.replace('_', ' ').title()}**: {value}" for key, value in stats.as_dict().items())
    lines.extend(["", "## Provenance", "", f"- Force: {manifest.get('force')}", f"- Actual dates: {', '.join(manifest.get('actual_dates_loaded', []))}", f"- Licence: {OGL}"])
    (reports / "latest.md").write_text("\n".join(lines), encoding="utf-8")


def write_evidence_documents(root: Path, documents: list[dict[str, Any]]) -> Path:
    path = root / "processed" / "evidence-documents.jsonl"
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for document in documents:
            handle.write(json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(path)
    return path


def _manifest_file(path: Path, root: Path, record_count: int | None = None) -> dict[str, Any]:
    return {
        "local_filename": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "record_count": record_count,
        "processing_status": "complete",
        "warnings": [],
        "errors": [],
        "licence": OGL,
    }


def load_policeuk(
    settings: Settings,
    *,
    download: bool | None = None,
    force_name: str | None = None,
    months_count: int | None = None,
) -> tuple[Graph, int, int, list[str], list[dict[str, Any]], PoliceUKStats]:
    started = time.perf_counter()
    root = settings.policeuk_raw_dir.parent
    raw_dir, processed_dir = settings.policeuk_raw_dir, settings.policeuk_processed_dir
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    should_download = settings.policeuk_download if download is None else download
    force_name = force_name or settings.policeuk_force
    force_id = normalize_force(force_name)
    months_count = months_count or settings.policeuk_months
    client = CachedPoliceUKClient(
        raw_dir, settings.policeuk_http_timeout_seconds,
        settings.policeuk_http_retries, settings.policeuk_user_agent,
    )
    archive: Path
    warnings: list[str] = []
    if should_download:
        available_months = latest_complete_months(client, months_count, False)
        archive = raw_dir / "policeuk-latest.zip"
        archive_sha = download_file(
            settings.policeuk_archive_url, archive,
            settings.policeuk_http_timeout_seconds, settings.policeuk_user_agent,
        )
        forces = client.get_json("https://data.police.uk/api/forces")
        match = next(
            (item for item in forces if item.get("id") == force_id or normalize_force(item.get("name", "")) == force_id),
            None,
        )
        if not match:
            raise ValueError(f"Police force not found in official API: {force_name}")
        force_id, force_name = str(match["id"]), str(match["name"])
        neighbourhoods = client.get_json(f"https://data.police.uk/api/{force_id}/neighbourhoods")
        (raw_dir / "force.json").write_text(json.dumps(match, ensure_ascii=False, indent=2), encoding="utf-8")
        (raw_dir / "neighbourhoods.json").write_text(json.dumps(neighbourhoods, ensure_ascii=False, indent=2), encoding="utf-8")
        boundary_dir = raw_dir / "boundaries"
        boundary_dir.mkdir(exist_ok=True)
        for item in neighbourhoods:
            boundary = client.get_json(f"https://data.police.uk/api/{force_id}/{item['id']}/boundary")
            (boundary_dir / f"{item['id']}.json").write_text(json.dumps(boundary, ensure_ascii=False, indent=2), encoding="utf-8")
            time.sleep(settings.policeuk_api_delay_seconds)
        manifest_seed = {"archive_sha256": archive_sha}
    else:
        manifest_path = root / "manifest.json"
        previous = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
        available_months = list(previous.get("actual_dates_loaded", []))[-months_count:]
        if not available_months:
            raise FileNotFoundError("Offline mode requires data/policeuk/manifest.json with actual dates")
        archives = sorted(raw_dir.glob("*.zip"))
        if not archives:
            raise FileNotFoundError("Offline mode requires a Police.uk ZIP in data/policeuk/raw")
        archive = archives[0]
        manifest_seed = {"archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}

    includes = set()
    if settings.policeuk_include_crimes:
        includes.add("crime")
    if settings.policeuk_include_outcomes:
        includes.add("outcome")
    if settings.policeuk_include_stops:
        includes.add("stop")
    rows_by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    files_by_kind: dict[str, str] = {}
    with ZipFile(archive) as zipped:
        members = select_archive_members(zipped.namelist(), force_id, available_months, includes)
        if not members:
            raise ValueError(f"No archive members matched force={force_id}, months={available_months}")
        for member in members:
            kind = archive_member_kind(member)
            if kind:
                rows_by_kind[kind].extend(read_csv_rows(zipped.read(member)))
                files_by_kind[kind] = member
                logger.info("policeuk_archive_member_selected", extra={"event": "policeuk_archive_member_selected", "source_file": member})
    for kind in includes:
        rows_by_kind[kind] = filter_rows_to_months(
            rows_by_kind[kind], kind, available_months
        )

    population_paths = sorted(
        [*raw_dir.glob("ons-population*.csv"), *raw_dir.glob("ons-population*.xlsx")]
    )
    populations: list[dict[str, Any]] = []
    if should_download and settings.policeuk_include_ons_population:
        lsoa_codes = {
            str(row.get("LSOA code") or "").strip()
            for row in rows_by_kind["crime"]
            if row.get("LSOA code")
        }
        populations, population_files = download_ons_population(
            settings.policeuk_ons_population_url,
            lsoa_codes,
            raw_dir,
            settings.policeuk_http_timeout_seconds,
            settings.policeuk_http_retries,
            settings.policeuk_user_agent,
        )
        population_paths = [raw_dir / name for name in population_files]
    elif settings.policeuk_include_ons_population:
        for population_path in population_paths:
            populations.extend(load_population_file(population_path))
        populations = sorted(
            {row["lsoa_code"]: row for row in populations}.values(),
            key=lambda row: row["lsoa_code"],
        )
    if settings.policeuk_include_ons_population and not population_paths:
        warnings.append("ONS population files absent; rates were not calculated")
    if population_paths:
        files_by_kind["population"] = ", ".join(path.name for path in population_paths)

    force_path = raw_dir / "force.json"
    force = json.loads(force_path.read_text(encoding="utf-8")) if force_path.is_file() else {"id": force_id, "name": force_name}
    neighbourhoods, boundaries = _load_boundaries(raw_dir)
    _write_processed(processed_dir, "crimes.csv", rows_by_kind["crime"])
    _write_processed(processed_dir, "outcomes.csv", rows_by_kind["outcome"])
    _write_processed(processed_dir, "stops.csv", rows_by_kind["stop"])
    _write_processed(processed_dir, "population.csv", populations)
    retrieved_at = datetime.now(UTC).isoformat()
    graph, documents, stats = build_policeuk_graph(
        rows_by_kind["crime"], rows_by_kind["outcome"], rows_by_kind["stop"],
        populations, force, neighbourhoods, boundaries, files_by_kind, retrieved_at,
    )
    stats.selected_files = sorted(set(files_by_kind.values()))
    stats.files_downloaded = (
        2 + 2 + len(neighbourhoods)
        if should_download
        else 0
    )
    stats.timings["total_prepare_seconds"] = round(time.perf_counter() - started, 3)
    manifest = {
        "source": "data.police.uk and Office for National Statistics",
        "source_type": "official open data",
        "force": force,
        "requested_dates": {"months": months_count},
        "actual_dates_loaded": available_months,
        "download_timestamp": retrieved_at,
        "local_filename": archive.name,
        "sha256": manifest_seed["archive_sha256"],
        "record_count": stats.rows_parsed,
        "processing_status": "complete",
        "warnings": warnings,
        "errors": [],
        "licence": OGL,
        "provenance": {
            "policeuk": "https://data.police.uk/",
            "ons": settings.policeuk_ons_population_url or "cached official ONS file",
            "coordinates": "anonymised approximate Police.uk published locations",
        },
        "selected_files": stats.selected_files,
        "files": [
            _manifest_file(archive, root, stats.rows_parsed),
            *[
                _manifest_file(path, root)
                for path in sorted(
                    [
                        *raw_dir.glob("force.json"),
                        *raw_dir.glob("neighbourhoods.json"),
                        *raw_dir.glob("boundaries/*.json"),
                        *population_paths,
                    ]
                )
                if path.is_file()
            ],
        ],
    }
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_evidence_documents(root, documents)
    write_report(root, stats, manifest)
    entities = len({subject for subject in graph.subjects(RDF.type) if isinstance(subject, URIRef)})
    relationships = sum(1 for _, predicate, obj in graph if isinstance(obj, URIRef) and predicate != RDF.type)
    return graph, entities, relationships, warnings, documents, stats
