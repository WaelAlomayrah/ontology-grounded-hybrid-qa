import csv
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from app.evaluation.baselines import MODES
from app.evaluation.metrics import coverage, entity_recall, graph_path_recall

RESULTS_DIR = Path("/app/data/evaluation-results")


async def run_evaluation(questions_path: Path, ask: Callable[[str, str], Awaitable[dict]]) -> dict:
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    results = {"created_at": datetime.now(UTC).isoformat(), "question_count": len(questions), "modes": {}}
    for mode in MODES:
        rows = []
        for item in questions:
            response = await ask(item["question"], mode)
            labels = [entity["label"] for entity in response.get("entities", [])]
            entities = response.get("entities", [])
            facts = [f"{f['subject_label']} {f['predicate_label']} {f['object_label']}" for f in response.get("retrieval", {}).get("graph_facts", [])]
            typed = sum(bool(entity.get("entity_type")) for entity in entities)
            rows.append({"id": item["id"], "keyword_coverage": coverage(response.get("answer", ""), item.get("expected_answer_keywords", [])), "entity_recall": entity_recall(labels, item.get("expected_entities", [])), "graph_path_recall": graph_path_recall(facts, item.get("expected_path", [])), "ontology_alignment": typed / len(entities) if entities else 0.0, "latency_ms": response.get("retrieval", {}).get("timings_ms", {}).get("total", 0), "answer_status": response.get("answer_status")})
        results["modes"][mode] = {"questions": rows, "averages": {metric: round(sum(row[metric] for row in rows)/len(rows), 4) for metric in ("keyword_coverage", "entity_recall", "graph_path_recall", "ontology_alignment", "latency_ms")}}
    hybrid = results["modes"]["hybrid"]["averages"]
    results["ontology"] = {
        "typed_entity_coverage": hybrid["ontology_alignment"],
        "relationship_grounding": hybrid["graph_path_recall"],
        "grounding_score": round((hybrid["ontology_alignment"] + hybrid["graph_path_recall"]) / 2, 4),
        "description": "Ontology grounding measures typed retrieved entities and expected relationship-path coverage in hybrid answers.",
    }
    vector = results["modes"]["vector_only"]["averages"]
    quality = lambda values: round((values["keyword_coverage"] + values["entity_recall"] + values["graph_path_recall"]) / 3, 4)
    without_ontology, with_ontology = quality(vector), quality(hybrid)
    evidence = lambda values: round((values["entity_recall"] + values["graph_path_recall"]) / 2, 4)
    results["ontology_ablation"] = {
        "without_ontology": without_ontology,
        "with_ontology": with_ontology,
        "absolute_gain": round(with_ontology - without_ontology, 4),
        "metrics": {
            "answer_accuracy": {"without": vector["keyword_coverage"], "with": hybrid["keyword_coverage"]},
            "evidence_accuracy": {"without": evidence(vector), "with": evidence(hybrid)},
            "entity_recall": {"without": vector["entity_recall"], "with": hybrid["entity_recall"]},
            "relationship_grounding": {"without": vector["graph_path_recall"], "with": hybrid["graph_path_recall"]},
            "latency_ms": {"without": vector["latency_ms"], "with": hybrid["latency_ms"]},
        },
        "method": "Without ontology uses vector-only semantic retrieval. With ontology uses hybrid retrieval with typed Fuseki graph evidence.",
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "latest.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    with (RESULTS_DIR / "latest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["mode", "id", "keyword_coverage", "entity_recall", "graph_path_recall", "ontology_alignment", "latency_ms", "answer_status"])
        writer.writeheader()
        for mode, mode_result in results["modes"].items():
            for row in mode_result["questions"]: writer.writerow({"mode": mode, **row})
    return results
