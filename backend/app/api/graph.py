from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.dependencies import get_fuseki
from app.models.api import PathRequest
from app.services.fuseki_service import FusekiService

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


@router.get("/classes")
async def classes(fuseki: FusekiService = Depends(get_fuseki)) -> list[dict[str, str]]:
    rows = await fuseki.query_select("PREFIX owl: <http://www.w3.org/2002/07/owl#> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?class ?label WHERE { ?class a owl:Class . OPTIONAL {?class rdfs:label ?label} } LIMIT 200")
    return [{key: value[key]["value"] for key in value} for value in rows]


@router.get("/ontology")
async def ontology(fuseki: FusekiService = Depends(get_fuseki)) -> dict[str, object]:
    class_rows = await fuseki.query_select("""
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?class ?label ?parent (COUNT(DISTINCT ?instance) AS ?instances) WHERE {
  ?class a owl:Class .
  OPTIONAL { ?class rdfs:label ?label }
  OPTIONAL { ?class rdfs:subClassOf ?parent FILTER(isIRI(?parent)) }
  OPTIONAL { ?instance a ?class }
} GROUP BY ?class ?label ?parent ORDER BY ?label LIMIT 200
""")
    property_rows = await fuseki.query_select("""
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?property ?label ?kind ?domain ?range WHERE {
  VALUES ?kind { owl:ObjectProperty owl:DatatypeProperty }
  ?property a ?kind .
  OPTIONAL { ?property rdfs:label ?label }
  OPTIONAL { ?property rdfs:domain ?domain }
  OPTIONAL { ?property rdfs:range ?range }
} ORDER BY ?label LIMIT 300
""")
    def flatten(rows: list[dict[str, object]]) -> list[dict[str, str]]:
        return [{key: str(value["value"]) for key, value in row.items()} for row in rows]  # type: ignore[index]
    return {"classes": flatten(class_rows), "properties": flatten(property_rows)}


@router.get("/entity")
async def entity(uri: str, fuseki: FusekiService = Depends(get_fuseki)): return await fuseki.get_entity(uri)


@router.get("/neighbors")
async def neighbors(uri: str, depth: int = Query(1, ge=1, le=3), fuseki: FusekiService = Depends(get_fuseki)): return await fuseki.get_neighbors(uri, depth)


@router.get("/search")
async def search(q: str = Query(min_length=1, max_length=200), fuseki: FusekiService = Depends(get_fuseki)): return await fuseki.search_labels(q)


@router.post("/path")
async def path(request: PathRequest, fuseki: FusekiService = Depends(get_fuseki)): return {"paths": await fuseki.get_shortest_explanatory_paths(request.source_uri, request.target_uri, request.max_hops)}


@router.get("/stats")
async def stats(fuseki: FusekiService = Depends(get_fuseki), settings: Settings = Depends(get_settings)) -> dict[str, object]:
    rows = await fuseki.query_select("SELECT (COUNT(*) AS ?triples) (COUNT(DISTINCT ?s) AS ?entities) WHERE { ?s ?p ?o }")
    values = rows[0] if rows else {}
    return {"dataset": settings.fuseki_dataset, "triple_count": int(values.get("triples", {}).get("value", 0)), "entity_count": int(values.get("entities", {}).get("value", 0))}
