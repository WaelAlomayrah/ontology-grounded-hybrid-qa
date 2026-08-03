import hashlib
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings
from app.models.graph import GraphData, GraphEdge, GraphNode, GraphPath
from app.models.retrieval import GraphFact
from app.services.workspace_state import active_dataset


def _literal(value: str) -> str:
    """Escape a string into a safe SPARQL literal; query structure remains static."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def _iri(value: str) -> str:
    if not re.fullmatch(r"https?://[^<>\"{}|\\^`\s]+", value):
        raise ValueError("Invalid HTTP(S) entity URI")
    return f"<{value}>"


class FusekiService:
    def __init__(self, settings: Settings, dataset: str | None = None) -> None:
        self.settings = settings
        self.auth = (settings.fuseki_user, settings.fuseki_password)
        self.dataset = dataset or active_dataset()

    @property
    def graph_uri(self) -> str:
        return f"http://example.org/graph/dataset/{quote(self.dataset, safe='')}"

    @property
    def dataset_url(self) -> str:
        return f"{self.settings.fuseki_base_url}/{self.settings.fuseki_dataset}"

    async def health_check(self) -> bool:
        try:
            await self.query_ask("ASK { ?s ?p ?o }")
            return True
        except Exception:
            return False

    async def query_select(self, query: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30, auth=self.auth) as client:
            response = await client.post(f"{self.dataset_url}/query", data={"query": query, "default-graph-uri": self.graph_uri}, headers={"Accept": "application/sparql-results+json"})
            response.raise_for_status()
            return response.json()["results"]["bindings"]

    async def query_ask(self, query: str) -> bool:
        async with httpx.AsyncClient(timeout=10, auth=self.auth) as client:
            response = await client.post(f"{self.dataset_url}/query", data={"query": query, "default-graph-uri": self.graph_uri}, headers={"Accept": "application/sparql-results+json"})
            response.raise_for_status()
            return bool(response.json()["boolean"])

    async def query_construct(self, query: str) -> str:
        async with httpx.AsyncClient(timeout=30, auth=self.auth) as client:
            response = await client.post(f"{self.dataset_url}/query", data={"query": query, "default-graph-uri": self.graph_uri}, headers={"Accept": "text/turtle"})
            response.raise_for_status()
            return response.text

    async def execute_update(self, update: str) -> None:
        async with httpx.AsyncClient(timeout=300, auth=self.auth) as client:
            response = await client.post(f"{self.dataset_url}/update", data={"update": update})
            response.raise_for_status()

    async def upload_rdf(self, data: bytes, content_type: str = "text/turtle") -> None:
        async with httpx.AsyncClient(timeout=120, auth=self.auth) as client:
            chunk_size = 25 * 1024 * 1024 if content_type == "application/n-triples" else len(data)
            offset = 0
            while offset < len(data):
                end = min(offset + chunk_size, len(data))
                if end < len(data):
                    newline = data.rfind(b"\n", offset, end)
                    end = newline + 1 if newline >= offset else end
                response = await client.post(
                    f"{self.dataset_url}/data",
                    params={"graph": self.graph_uri},
                    content=data[offset:end],
                    headers={"Content-Type": content_type},
                )
                response.raise_for_status()
                offset = end

    async def upload_rdf_file(
        self,
        path: Path,
        content_type: str = "application/n-triples",
        chunk_size: int = 2 * 1024 * 1024,
    ) -> None:
        """Upload an RDF file in bounded newline-aligned chunks."""
        async with httpx.AsyncClient(timeout=180, auth=self.auth) as client:
            with path.open("rb") as handle:
                pending = b""
                while block := handle.read(chunk_size):
                    pending += block
                    newline = pending.rfind(b"\n")
                    if newline < 0:
                        continue
                    payload, pending = pending[: newline + 1], pending[newline + 1 :]
                    response = await client.post(
                        f"{self.dataset_url}/data",
                        params={"graph": self.graph_uri},
                        content=payload,
                        headers={"Content-Type": content_type},
                    )
                    response.raise_for_status()
                if pending:
                    response = await client.post(
                        f"{self.dataset_url}/data",
                        params={"graph": self.graph_uri},
                        content=pending,
                        headers={"Content-Type": content_type},
                    )
                    response.raise_for_status()

    async def delete_all(self) -> None:
        await self.execute_update(f"CLEAR SILENT GRAPH <{self.graph_uri}>")

    async def exists(self) -> bool:
        return await self.query_ask("ASK { ?s ?p ?o }")

    async def preserve_legacy_default_graph(self) -> bool:
        """Copy the legacy default graph once into this dataset's named graph."""
        if await self.exists():
            return True
        async with httpx.AsyncClient(timeout=10, auth=self.auth) as client:
            response = await client.post(
                f"{self.dataset_url}/query",
                data={"query": "ASK { ?s ?p ?o }"},
                headers={"Accept": "application/sparql-results+json"},
            )
            response.raise_for_status()
            has_legacy_data = bool(response.json()["boolean"])
        if has_legacy_data:
            await self.execute_update(f"COPY DEFAULT TO GRAPH <{self.graph_uri}>")
        return has_legacy_data

    async def search_labels(self, text: str, limit: int = 20) -> list[dict[str, str]]:
        limit = min(max(limit, 1), self.settings.graph_result_limit)
        query = f'''PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?entity ?label ?type WHERE {{ ?entity rdfs:label ?label . OPTIONAL {{ ?entity a ?type }} FILTER(CONTAINS(LCASE(STR(?label)), LCASE({_literal(text)}))) }} LIMIT {limit}'''
        rows = await self.query_select(query)
        return [{key: values[key]["value"] for key in values} for values in rows]

    async def get_entity(self, uri: str) -> GraphData:
        return await self.get_neighbors(uri, 0)

    async def get_neighbors(self, uri: str, depth: int = 1) -> GraphData:
        entity = _iri(uri)
        depth = min(max(depth, 0), 3)
        path = (
            "(!<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>|"
            "^!<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>)"
            if depth
            else None
        )
        # Static bounded property path; never accepts user query syntax.
        selector = f"{entity} {path}{{0,{depth}}} ?s ." if depth else f"BIND({entity} AS ?s)"
        query = f'''PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?s ?sLabel ?sType ?p ?pLabel ?o ?oLabel ?oType WHERE {{ {selector} ?s ?p ?o .
FILTER(isIRI(?o)) OPTIONAL {{ ?s rdfs:label ?sLabel }} OPTIONAL {{ ?s a ?sType }} OPTIONAL {{ ?p rdfs:label ?pLabel }} OPTIONAL {{ ?o rdfs:label ?oLabel }} OPTIONAL {{ ?o a ?oType }} }} LIMIT {self.settings.graph_result_limit}'''
        return self._rows_to_graph(await self.query_select(query))

    async def facts_for_labels(self, labels: list[str]) -> tuple[GraphData, list[GraphFact]]:
        graph = GraphData()
        for label in labels[:10]:
            for entity in await self.search_labels(label, 5):
                part = await self.get_neighbors(entity["entity"], 1)
                graph.nodes.extend(part.nodes)
                graph.edges.extend(part.edges)
        graph.nodes = list({n.id: n for n in graph.nodes}.values())
        graph.edges = list({e.id: e for e in graph.edges}.values())
        labels_by_id = {n.id: n.label for n in graph.nodes}
        facts = [GraphFact(id=f"G{i+1}", subject=e.source, subject_label=labels_by_id.get(e.source, e.source), predicate=e.predicate, predicate_label=e.label, object=e.target, object_label=labels_by_id.get(e.target, e.target)) for i, e in enumerate(graph.edges)]
        return graph, facts

    async def get_shortest_explanatory_paths(self, source: str, target: str, max_hops: int = 3) -> list[GraphPath]:
        # The bounded neighborhood is traversed locally for readable paths.
        graph = await self.get_neighbors(source, min(max_hops, 3))
        adjacency: dict[str, list[tuple[str, str]]] = {}
        for edge in graph.edges:
            adjacency.setdefault(edge.source, []).append((edge.target, edge.label))
            adjacency.setdefault(edge.target, []).append((edge.source, edge.label))
        queue: list[tuple[str, list[str], list[str]]] = [(source, [source], [])]
        while queue:
            current, nodes, predicates = queue.pop(0)
            if current == target:
                return [GraphPath(nodes=nodes, predicates=predicates, text=" -> ".join(nodes))]
            if len(predicates) < max_hops:
                queue.extend((nxt, nodes + [nxt], predicates + [pred]) for nxt, pred in adjacency.get(current, []) if nxt not in nodes)
        return []

    def _rows_to_graph(self, rows: list[dict[str, Any]]) -> GraphData:
        nodes: dict[str, GraphNode] = {}
        edges: dict[str, GraphEdge] = {}
        for row in rows:
            source, target, predicate = row["s"]["value"], row["o"]["value"], row["p"]["value"]
            nodes[source] = GraphNode(id=source, label=row.get("sLabel", {}).get("value", source.rsplit("/", 1)[-1]), type=row.get("sType", {}).get("value", "Thing").rsplit("/", 1)[-1])
            nodes[target] = GraphNode(id=target, label=row.get("oLabel", {}).get("value", target.rsplit("/", 1)[-1]), type=row.get("oType", {}).get("value", "Thing").rsplit("/", 1)[-1])
            edge_id = hashlib.sha1(f"{source}|{predicate}|{target}".encode()).hexdigest()[:16]
            edges[edge_id] = GraphEdge(id=edge_id, source=source, target=target, predicate=predicate, label=row.get("pLabel", {}).get("value", predicate.rsplit("/", 1)[-1]))
        return GraphData(nodes=list(nodes.values()), edges=list(edges.values()))
