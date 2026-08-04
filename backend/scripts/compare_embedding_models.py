"""Offline, non-destructive retrieval comparison for the Arabic enterprise corpus."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import torch
from sentence_transformers import SentenceTransformer

from app.config import get_settings
from app.ingestion.arabic_enterprise_loader import load_arabic_enterprise
from app.ingestion.loader import entity_documents

DEFAULT_MODELS = (
    "intfloat/multilingual-e5-large",
    "ibm-granite/granite-embedding-311m-multilingual-r2",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare embedding retrieval on Arabic questions")
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--max-seq-length", type=int, default=512)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/app/data/evaluation-results/embedding-model-comparison.json"),
    )
    return parser.parse_args()


def prefixed(model_name: str, kind: str, values: list[str]) -> list[str]:
    if "e5" not in model_name.lower():
        return values
    return [f"{kind}: {value}" for value in values]


def evaluate_ranking(
    scores: torch.Tensor,
    questions: list[dict[str, Any]],
    evidence_texts: list[str],
) -> dict[str, float]:
    rankings = torch.topk(scores, k=min(10, scores.shape[1]), dim=1).indices.cpu().tolist()
    totals = {"recall@1": 0.0, "recall@5": 0.0, "recall@10": 0.0, "hit@5": 0.0, "mrr@10": 0.0}
    for question, ranking in zip(questions, rankings, strict=True):
        expected = [str(value).casefold() for value in question.get("expected_entities", [])]
        answer_terms = [
            str(value).casefold() for value in question.get("expected_answer_keywords", [])
        ]
        ranked_evidence = [evidence_texts[index].casefold() for index in ranking]
        for cutoff in (1, 5, 10):
            joined = "\n".join(ranked_evidence[:cutoff])
            recalled = sum(term in joined for term in expected) / len(expected) if expected else 1.0
            totals[f"recall@{cutoff}"] += recalled
        top_five = "\n".join(ranked_evidence[:5])
        totals["hit@5"] += float(all(term in top_five for term in answer_terms))
        first_relevant = next(
            (
                rank
                for rank, evidence in enumerate(ranked_evidence, 1)
                if any(term in evidence for term in answer_terms)
            ),
            None,
        )
        totals["mrr@10"] += 1.0 / first_relevant if first_relevant else 0.0
    return {name: round(value / len(questions), 4) for name, value in totals.items()}


def main() -> None:
    args = parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; this comparison must run in the GPU image")
    settings = get_settings()
    graph, _, _, warnings, prepared = load_arabic_enterprise(
        settings.arabic_enterprise_dataset_path
    )
    if warnings:
        raise RuntimeError("; ".join(warnings))
    graph_documents = entity_documents(graph, "arabic_enterprise")
    by_uri = {document["entity_uri"]: document for document in graph_documents}
    by_uri.update({document["entity_uri"]: document for document in prepared})
    documents = list(by_uri.values())
    evidence_texts = [f"{document['label']}\n{document['text']}" for document in documents]
    questions_path = settings.arabic_enterprise_dataset_path / "evaluation_questions_ar.json"
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    query_texts = [str(item["question"]) for item in questions]

    result: dict[str, Any] = {
        "device": torch.cuda.get_device_name(0),
        "document_count": len(documents),
        "question_count": len(questions),
        "max_seq_length": args.max_seq_length,
        "batch_size": args.batch_size,
        "models": {},
    }
    for model_name in args.models:
        torch.cuda.empty_cache()
        load_started = time.perf_counter()
        model = SentenceTransformer(model_name, device="cuda")
        model.max_seq_length = args.max_seq_length
        # ModernBERT enables torch.compile by default; the slim runtime intentionally
        # has no C compiler, so use its equivalent eager execution path.
        transformer = model[0]
        auto_model = getattr(transformer, "auto_model", None)
        if auto_model is not None and hasattr(auto_model.config, "reference_compile"):
            auto_model.config.reference_compile = False
        load_seconds = time.perf_counter() - load_started

        corpus_started = time.perf_counter()
        corpus_embeddings = model.encode(
            prefixed(model_name, "passage", evidence_texts),
            batch_size=args.batch_size,
            normalize_embeddings=True,
            convert_to_tensor=True,
            show_progress_bar=True,
        )
        torch.cuda.synchronize()
        corpus_seconds = time.perf_counter() - corpus_started

        query_started = time.perf_counter()
        query_embeddings = model.encode(
            prefixed(model_name, "query", query_texts),
            batch_size=args.batch_size,
            normalize_embeddings=True,
            convert_to_tensor=True,
            show_progress_bar=True,
        )
        scores = query_embeddings @ corpus_embeddings.T
        torch.cuda.synchronize()
        query_seconds = time.perf_counter() - query_started
        metrics = evaluate_ranking(scores, questions, evidence_texts)
        result["models"][model_name] = {
            **metrics,
            "dimension": int(corpus_embeddings.shape[1]),
            "load_seconds": round(load_seconds, 3),
            "corpus_encoding_seconds": round(corpus_seconds, 3),
            "documents_per_second": round(len(documents) / corpus_seconds, 2),
            "query_batch_seconds": round(query_seconds, 3),
            "mean_query_latency_ms": round(query_seconds * 1000 / len(questions), 3),
            "peak_gpu_memory_mb": round(torch.cuda.max_memory_allocated() / 1024**2, 1),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        del model, corpus_embeddings, query_embeddings, scores

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
