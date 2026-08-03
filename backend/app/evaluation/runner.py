import csv
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.evaluation.baselines import MODES
from app.evaluation.metrics import coverage, entity_recall, graph_path_recall

RESULTS_DIR = Path("/app/data/evaluation-results")


async def run_evaluation(
    questions_path: Path,
    ask: Callable[[str, str], Awaitable[dict]],
    result_name: str = "latest",
    progress: Callable[[str, int, int], None] | None = None,
) -> dict:
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    results: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "question_count": len(questions),
        "modes": {},
    }
    for mode in MODES:
        rows = []
        for index, item in enumerate(questions, start=1):
            response = await ask(item["question"], mode)
            labels = [entity["label"] for entity in response.get("entities", [])]
            graph_nodes = response.get("graph", {}).get("nodes", [])
            facts = [
                f"{f['subject_label']} {f['predicate_label']} {f['object_label']}"
                for f in response.get("retrieval", {}).get("graph_facts", [])
            ]
            typed = sum(
                bool(node.get("type")) and node.get("type") != "Thing"
                for node in graph_nodes
            )
            expected_path = item.get("expected_path", [])
            rows.append(
                {
                    "id": item["id"],
                    "keyword_coverage": coverage(
                        response.get("answer", ""), item.get("expected_answer_keywords", [])
                    ),
                    "entity_recall": entity_recall(labels, item.get("expected_entities", [])),
                    "graph_path_recall": graph_path_recall(facts, expected_path),
                    "path_applicable": bool(expected_path),
                    "ontology_alignment": typed / len(graph_nodes) if graph_nodes else 0.0,
                    "graph_activated": bool(graph_nodes or facts),
                    "latency_ms": response.get("retrieval", {})
                    .get("timings_ms", {})
                    .get("total", 0),
                    "answer_status": response.get("answer_status"),
                }
            )
            if progress:
                progress(mode, index, len(questions))
        results["modes"][mode] = {
            "questions": rows,
            "averages": {
                metric: round(
                    sum(row[metric] for row in (
                        [item for item in rows if item["path_applicable"]]
                        if metric == "graph_path_recall"
                        else rows
                    ))
                    / max(
                        1,
                        len(
                            [item for item in rows if item["path_applicable"]]
                            if metric == "graph_path_recall"
                            else rows
                        ),
                    ),
                    4,
                )
                for metric in ("keyword_coverage", "entity_recall", "graph_path_recall", "ontology_alignment", "latency_ms")
            },
        }
        results["modes"][mode]["averages"]["graph_activation_rate"] = round(
            sum(row["graph_activated"] for row in rows) / len(rows), 4
        )
    hybrid = results["modes"]["hybrid"]["averages"]
    results["ontology"] = {
        "typed_entity_coverage": hybrid["ontology_alignment"],
        "relationship_grounding": hybrid["graph_path_recall"],
        "grounding_score": round(
            (hybrid["ontology_alignment"] + hybrid["graph_path_recall"]) / 2, 4
        ),
        "graph_activation_rate": hybrid["graph_activation_rate"],
        "description": "Ontology grounding measures typed retrieved entities and expected relationship-path coverage in hybrid answers.",
    }
    vector = results["modes"]["vector_only"]["averages"]

    def quality(values: dict[str, float]) -> float:
        return round(
            (values["keyword_coverage"] + values["entity_recall"] + values["graph_path_recall"])
            / 3,
            4,
        )

    without_ontology, with_ontology = quality(vector), quality(hybrid)

    def evidence(values: dict[str, float]) -> float:
        return round((values["entity_recall"] + values["graph_path_recall"]) / 2, 4)

    results["ontology_ablation"] = {
        "without_ontology": without_ontology,
        "with_ontology": with_ontology,
        "absolute_gain": round(with_ontology - without_ontology, 4),
        "metrics": {
            "answer_accuracy": {
                "without": vector["keyword_coverage"],
                "with": hybrid["keyword_coverage"],
            },
            "evidence_accuracy": {"without": evidence(vector), "with": evidence(hybrid)},
            "entity_recall": {"without": vector["entity_recall"], "with": hybrid["entity_recall"]},
            "relationship_grounding": {
                "without": vector["graph_path_recall"],
                "with": hybrid["graph_path_recall"],
            },
            "latency_ms": {"without": vector["latency_ms"], "with": hybrid["latency_ms"]},
        },
        "method": "Without ontology uses vector-only semantic retrieval. With ontology uses hybrid retrieval with typed Fuseki graph evidence.",
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / f"{result_name}.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    (RESULTS_DIR / "latest.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    with (RESULTS_DIR / f"{result_name}.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "mode",
                "id",
                "keyword_coverage",
                "entity_recall",
                "graph_path_recall",
                "ontology_alignment",
                "latency_ms",
                "graph_activated",
                "path_applicable",
                "answer_status",
            ],
        )
        writer.writeheader()
        for mode, mode_result in results["modes"].items():
            for row in mode_result["questions"]:
                writer.writerow({"mode": mode, **row})
    return results
