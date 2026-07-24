from pathlib import Path

import pytest

from app.config import Settings
from app.evaluation.metrics import coverage, token_f1
from app.ingestion.csv_loader import load_sample_csvs
from app.ingestion.loader import entity_documents
from app.ingestion.mappings import SOURCE_COLUMNS, detect_column
from app.models.api import QuestionRequest
from app.models.retrieval import RetrievalItem
from app.retrieval.context_builder import build_context
from app.retrieval.hybrid_retriever import deduplicate_results, hybrid_score
from app.retrieval.intent_classifier import classify_intent

SAMPLE = Path(__file__).parents[3] / "data" / "sample"

def test_settings_validate_weights():
    with pytest.raises(ValueError): Settings(hybrid_vector_weight=.7, hybrid_graph_weight=.7)
def test_question_validation():
    assert QuestionRequest(question="  What   system? ").question == "What system?"
    with pytest.raises(ValueError): QuestionRequest(question="   ")
def test_intent_rules():
    assert "aggregation" in classify_intent("How many projects exist?")
    assert "multi_hop" in classify_intent("Who manages the department that owns the system?")
def test_hybrid_and_dedupe():
    assert hybrid_score(.8,.6,.55,.45) == pytest.approx(.71)
    def item(score): return RetrievalItem(id=str(score),entity_uri="u",label="x",text="x",source="s",score=score)
    assert deduplicate_results([item(.1),item(.9)])[0].score == .9
def test_context_limit():
    item=RetrievalItem(id="1",entity_uri="u",label="Label",text="x"*500,source="s")
    assert len(build_context([item],[],[item],["s"],30,1000)) <= 1000
def test_column_detection(): assert detect_column(["head","tail"],SOURCE_COLUMNS) == "head"
def test_sample_mapping_and_text():
    graph,entities,relationships=load_sample_csvs(SAMPLE)
    assert entities == 43 and relationships >= 25
    assert any("Entity: Finance Department" in d["text"] for d in entity_documents(graph,"sample"))
def test_metrics():
    assert token_f1("Alpha Technologies","Alpha Technologies") == 1
    assert coverage("supplied by Alpha Technologies",["Alpha Technologies"]) == 1

