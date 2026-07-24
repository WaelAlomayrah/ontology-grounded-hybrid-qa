from app.models.retrieval import GraphFact, RetrievalItem


def build_context(
    entities: list[RetrievalItem], facts: list[GraphFact], vectors: list[RetrievalItem],
    sources: list[str], max_items: int, max_characters: int,
) -> str:
    sections = ["Identified entities"]
    lines = [f"[E{i+1}] {item.label} ({item.entity_type}) <{item.entity_uri}>" for i, item in enumerate(entities)]
    sections.append("\n".join(lines) or "None")
    sections.append("Graph facts")
    sections.append("\n".join(f"[{fact.id}] {fact.subject_label} --{fact.predicate_label}--> {fact.object_label}" for fact in facts) or "None")
    sections.append("Relationship paths\nPaths are represented by connected graph facts above.")
    sections.append("Semantic matches")
    sections.append("\n".join(f"[V{i+1}] {item.text}" for i, item in enumerate(vectors)) or "None")
    sections.append("Dataset/source metadata\n" + (", ".join(sources) or "None"))
    output: list[str] = []
    seen: set[str] = set()
    item_count = 0
    for line in "\n".join(sections).splitlines():
        normalized = line.strip().lower()
        if normalized and normalized in seen:
            continue
        if normalized:
            seen.add(normalized)
            item_count += 1
        candidate = "\n".join(output + [line])
        if item_count > max_items or len(candidate) > max_characters:
            break
        output.append(line)
    return "\n".join(output)

