import re

from app.models.retrieval import GraphFact, RetrievalResult
from app.services.language_service import detect_language


class OntologyService:
    @staticmethod
    def confidence(result: RetrievalResult) -> float:
        evidence = len(result.retrieval.graph_facts) + len(result.retrieval.vector_results)
        diversity = int(bool(result.retrieval.graph_facts)) + int(bool(result.retrieval.vector_results))
        if not evidence:
            return 0.0
        confidence = min(0.95, 0.15 + min(evidence, 8) * 0.07 + diversity * 0.1)
        label_uris: dict[str, set[str]] = {}
        for entity in result.entities:
            label_uris.setdefault(entity.label.casefold(), set()).add(entity.entity_uri)
        largest_ambiguity = max((len(uris) for uris in label_uris.values()), default=1)
        if largest_ambiguity > 1:
            confidence -= min(0.3, (largest_ambiguity - 1) * 0.04)
        return round(max(0.0, confidence), 2)

    @staticmethod
    def ambiguity_answer(result: RetrievalResult) -> str | None:
        """Return a deterministic answer when a question names several distinct records."""
        question = result.question.casefold()
        groups: dict[str, list[str]] = {}
        display_labels: dict[str, str] = {}
        for entity in result.entities:
            key = entity.label.casefold()
            if entity.label and entity.label.casefold() in question:
                display_labels[key] = entity.label
                if entity.entity_uri not in groups.setdefault(key, []):
                    groups[key].append(entity.entity_uri)
        ambiguous = next(
            ((key, uris) for key, uris in groups.items() if len(uris) > 1),
            None,
        )
        if ambiguous is None:
            return None

        key, uris = ambiguous
        question_terms = {
            term for term in re.findall(r"[\w\u0600-\u06ff]+", question)
            if len(term) > 2
        }
        facts = [
            fact for fact in result.retrieval.graph_facts
            if fact.subject in uris
            and question_terms.intersection(
                term.casefold()
                for term in re.findall(r"[\w\u0600-\u06ff]+", fact.predicate_label)
                if len(term) > 2
            )
        ]
        if not facts:
            return None

        # Keep one direct assertion per record and preserve its evidence identifier.
        by_subject: dict[str, GraphFact] = {}
        for fact in facts:
            by_subject.setdefault(fact.subject, fact)
        facts = list(by_subject.values())
        label = display_labels[key]
        if detect_language(result.question) == "ar":
            lines = [
                f"- `{fact.subject.rsplit('/', 1)[-1]}`: "
                f"{fact.predicate_label} «{fact.object_label}» [{fact.id}]"
                for fact in facts
            ]
            return (
                f"الاسم «{label}» غير فريد في البيانات؛ يوجد {len(uris)} سجلات موظفين "
                "مختلفة بهذا الاسم، ولا تمثل شخصًا واحدًا يعمل في عدة إدارات.\n\n"
                + "\n".join(lines)
                + "\n\nلتحديد إدارة واحدة بدقة، يلزم رقم الموظف أو سمة مميزة أخرى."
            )
        lines = [
            f"- `{fact.subject.rsplit('/', 1)[-1]}`: "
            f"{fact.predicate_label} “{fact.object_label}” [{fact.id}]"
            for fact in facts
        ]
        return (
            f"“{label}” is ambiguous: {len(uris)} distinct employee records share this "
            "label; they are not one person working in several departments.\n\n"
            + "\n".join(lines)
            + "\n\nAn employee ID or another distinguishing attribute is required for one answer."
        )
