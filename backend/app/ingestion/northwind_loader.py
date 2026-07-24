from pathlib import Path
from zipfile import ZipFile

import pandas as pd
from rdflib import OWL, RDF, RDFS, Graph, Literal, Namespace, URIRef

NW = Namespace("http://example.org/northwind/")

PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "categories": ("categoryID",), "customers": ("customerID",), "employees": ("employeeID",),
    "orders": ("orderID",), "products": ("productID",), "regions": ("regionID",),
    "shippers": ("shipperID",), "suppliers": ("supplierID",), "territories": ("territoryID",),
    "order-details": ("orderID", "productID"), "employee-territories": ("employeeID", "territoryID"),
}

LABEL_COLUMNS = ("productName", "companyName", "categoryName", "lastName", "territoryDescription", "regionDescription", "shipName", "contactName")

RELATIONS = {
    "products": {"supplierID": ("suppliers", "suppliedBy"), "categoryID": ("categories", "inCategory")},
    "orders": {"customerID": ("customers", "orderedBy"), "employeeID": ("employees", "handledBy"), "shipVia": ("shippers", "shippedBy")},
    "territories": {"regionID": ("regions", "inRegion")},
    "order-details": {"orderID": ("orders", "forOrder"), "productID": ("products", "forProduct")},
    "employee-territories": {"employeeID": ("employees", "hasEmployee"), "territoryID": ("territories", "hasTerritory")},
    "employees": {"reportsTo": ("employees", "reportsTo")},
}


def _uri(table: str, row: dict[str, object]) -> URIRef:
    key = "-".join(str(row.get(column, "")) for column in PRIMARY_KEYS[table])
    return NW[f"{table}/{key}"]


def load_northwind(directory: Path) -> tuple[Graph, int, int, list[str]]:
    archive = next(directory.glob("*.zip"), None)
    if archive is None:
        raise FileNotFoundError(f"No Northwind ZIP found in {directory}")
    frames: dict[str, pd.DataFrame] = {}; warnings: list[str] = []
    with ZipFile(archive) as zipped:
        for name in zipped.namelist():
            if name.lower().endswith(".csv"):
                try:
                    frames[Path(name).stem.lower()] = pd.read_csv(zipped.open(name)).fillna("")
                except pd.errors.ParserError:
                    frames[Path(name).stem.lower()] = pd.read_csv(zipped.open(name), engine="python", on_bad_lines="skip").fillna("")
                    warnings.append(f"Skipped malformed legacy rows in {Path(name).name}")
    graph, entities, relationships = Graph(), 0, 0
    graph.bind("nw", NW)
    for table, frame in sorted(frames.items()):
        if table not in PRIMARY_KEYS:
            continue
        class_uri = NW[table.replace("-", "_").title().replace("_", "")]
        graph.add((class_uri, RDF.type, OWL.Class)); graph.add((class_uri, RDFS.label, Literal(table.replace("-", " ").title())))
        for row in frame.to_dict("records"):
            subject = _uri(table, row)
            graph.add((subject, RDF.type, class_uri))
            label = next((str(row[column]) for column in LABEL_COLUMNS if column in row and str(row[column])), " / ".join(str(row.get(column, "")) for column in PRIMARY_KEYS[table]))
            graph.add((subject, RDFS.label, Literal(label)))
            for column, value in row.items():
                if value != "": graph.add((subject, NW[column], Literal(value)))
            entities += 1
    for table, relations in RELATIONS.items():
        for row in frames.get(table, pd.DataFrame()).to_dict("records"):
            source = _uri(table, row)
            for column, (target_table, predicate) in relations.items():
                value = row.get(column, "")
                if value == "": continue
                target_row = {PRIMARY_KEYS[target_table][0]: value}
                graph.add((source, NW[predicate], _uri(target_table, target_row))); relationships += 1
                graph.add((NW[predicate], RDF.type, OWL.ObjectProperty)); graph.add((NW[predicate], RDFS.label, Literal(predicate)))
    return graph, entities, relationships, warnings
