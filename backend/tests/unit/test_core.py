from pathlib import Path

import pytest
from rdflib import RDF, RDFS, URIRef

from app.config import Settings
from app.evaluation.metrics import coverage, token_f1
from app.ingestion.csv_loader import load_sample_csvs
from app.ingestion.loader import entity_documents
from app.ingestion.kg2qa_loader import load_kg2qa
from app.ingestion.mappings import SOURCE_COLUMNS, detect_column
from app.models.api import EvaluationRunRequest, QuestionRequest
from app.models.retrieval import GraphFact, RetrievalItem
from app.retrieval.context_builder import build_context
from app.retrieval.hybrid_retriever import deduplicate_results, hybrid_score
from app.retrieval.intent_classifier import classify_intent, extract_entity_mentions

SAMPLE = Path(__file__).parents[3] / "data" / "sample"

def test_settings_validate_weights():
    with pytest.raises(ValueError): Settings(hybrid_vector_weight=.7, hybrid_graph_weight=.7)
def test_question_validation():
    assert QuestionRequest(question="  What   system? ").question == "What system?"
    with pytest.raises(ValueError): QuestionRequest(question="   ")
def test_intent_rules():
    assert "aggregation" in classify_intent("How many projects exist?")
    assert "multi_hop" in classify_intent("Who manages the department that owns the system?")
    assert extract_entity_mentions('What is "fitting procedures" relevant to?') == [
        "fitting procedures"
    ]
    assert extract_entity_mentions("في أي إدارة يعمل الموظف سعود العمري؟") == [
        "سعود العمري"
    ]
    assert extract_entity_mentions("من أعد المستند «إجراء إدارة البيانات رقم 1»؟") == [
        "إجراء إدارة البيانات رقم 1"
    ]
def test_hybrid_and_dedupe():
    assert hybrid_score(.8,.6,.55,.45) == pytest.approx(.71)
    def item(score): return RetrievalItem(id=str(score),entity_uri="u",label="x",text="x",source="s",score=score)
    assert deduplicate_results([item(.1),item(.9)])[0].score == .9
def test_context_limit():
    item=RetrievalItem(id="1",entity_uri="u",label="Label",text="x"*500,source="s")
    assert len(build_context([item],[],[item],["s"],30,1000)) <= 1000

def test_context_prioritizes_relationships_and_marks_duplicate_labels():
    entities = [
        RetrievalItem(
            id=str(index), entity_uri=f"employee:{index}", label="سعود العمري",
            entity_type="Employee", text="employee", source="arabic_enterprise",
        )
        for index in range(7)
    ]
    fact = GraphFact(
        id="G1", subject="employee:1", subject_label="سعود العمري",
        predicate="worksIn", predicate_label="يعمل في",
        object="department:sales", object_label="المبيعات",
    )
    context = build_context(
        entities * 5, [fact], [], ["arabic_enterprise"], 30, 12000,
        "في أي إدارة يعمل سعود العمري؟",
    )
    assert "[G1]" in context
    assert "يعمل في" in context
    assert "7 distinct records" in context
def test_column_detection(): assert detect_column(["head","tail"],SOURCE_COLUMNS) == "head"
def test_sample_mapping_and_text():
    graph,entities,relationships=load_sample_csvs(SAMPLE)
    assert entities == 43 and relationships >= 25
    assert any("Entity: Finance Department" in d["text"] for d in entity_documents(graph,"sample"))
def test_metrics():
    assert token_f1("Alpha Technologies","Alpha Technologies") == 1
    assert coverage("supplied by Alpha Technologies",["Alpha Technologies"]) == 1
    from app.evaluation.metrics import graph_path_recall
    assert graph_path_recall([], []) == 0

def test_evaluation_request_accepts_kg2qa():
    request = EvaluationRunRequest(dataset="kg2qa", embedding_model="granite-311m-r2")
    assert request.dataset == "kg2qa"

def test_kg2qa_uses_name_as_label_and_label_as_class():
    graph, entities, relationships, _ = load_kg2qa(
        Path(__file__).parents[3] / "data" / "KG2QA_ontology_dataset"
    )
    entity = URIRef("http://example.org/kg2qa/ACT007")
    assert entities > 0 and relationships > 0
    assert str(graph.value(entity, RDFS.label)) == "fitting procedures"
    assert graph.value(entity, RDF.type) == URIRef("http://example.org/kg2qa/ACT")
