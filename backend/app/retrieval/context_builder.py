import re
from collections import OrderedDict

from app.models.retrieval import GraphFact, RetrievalItem


def _is_type_fact(fact: GraphFact) -> bool:
    predicate = fact.predicate.lower().rstrip("/#")
    return predicate.endswith("rdf-syntax-ns#type") or predicate.endswith("/type")


def _question_relevance(fact: GraphFact, question: str) -> int:
    question_terms = {
        term.lower() for term in re.findall(r"[\w\u0600-\u06ff]+", question)
        if len(term) > 2
    }
    relation_terms = {
        term.lower()
        for term in re.findall(r"[\w\u0600-\u06ff]+", fact.predicate_label)
        if len(term) > 2
    }
    return len(question_terms & relation_terms)


def _group_entities(entities: list[RetrievalItem]) -> list[str]:
    groups: OrderedDict[tuple[str, str], list[str]] = OrderedDict()
    for item in entities:
        groups.setdefault((item.label, item.entity_type), [])
        if item.entity_uri not in groups[(item.label, item.entity_type)]:
            groups[(item.label, item.entity_type)].append(item.entity_uri)

    lines: list[str] = []
    for index, ((label, entity_type), uris) in enumerate(groups.items(), 1):
        qualifier = f" — {len(uris)} distinct records" if len(uris) > 1 else ""
        lines.append(
            f"[E{index}] {label} ({entity_type}){qualifier}: "
            + ", ".join(f"<{uri}>" for uri in uris)
        )
    return lines


def build_context(
    entities: list[RetrievalItem], facts: list[GraphFact], vectors: list[RetrievalItem],
    sources: list[str], max_items: int, max_characters: int, question: str = "",
) -> str:
    """Build a bounded context while reserving most of the budget for direct facts."""
    fact_budget = max(1, int(max_items * 0.7)) if facts else 0
    entity_budget = max(1, int(max_items * 0.15)) if entities else 0
    vector_budget = max(0, max_items - fact_budget - entity_budget)

    # Type assertions are useful, but direct relationships answer most questions.
    ordered_facts = sorted(
        facts,
        key=lambda fact: (_is_type_fact(fact), -_question_relevance(fact, question)),
    )
    fact_lines = [
        (
            f"[{fact.id}] {fact.subject_label} <{fact.subject}> "
            f"--{fact.predicate_label}--> {fact.object_label} <{fact.object}>"
        )
        for fact in ordered_facts[:fact_budget]
    ]
    entity_lines = _group_entities(entities)[:entity_budget]
    vector_lines = [
        f"[V{i + 1}] {item.text}" for i, item in enumerate(vectors[:vector_budget])
    ]

    sections = [
        (
            "Evidence note\nRepeated labels with different URIs are distinct records. "
            "Do not merge them; explicitly report ambiguity when they have different relationships."
        ),
        "Graph facts\n" + ("\n".join(fact_lines) or "None"),
        "Identified entities\n" + ("\n".join(entity_lines) or "None"),
        "Relationship paths\nPaths are represented by connected graph facts above.",
        "Semantic matches\n" + ("\n".join(vector_lines) or "None"),
        "Dataset/source metadata\n" + (", ".join(sources) or "None"),
    ]

    output: list[str] = []
    for section in sections:
        candidate = "\n\n".join(output + [section])
        if len(candidate) <= max_characters:
            output.append(section)
            continue
        remaining = max_characters - len("\n\n".join(output)) - (2 if output else 0)
        if remaining > 0:
            output.append(section[:remaining])
        break
    return "\n\n".join(output)
