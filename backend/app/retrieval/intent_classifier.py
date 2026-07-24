import re


def classify_intent(question: str) -> list[str]:
    text = " ".join(question.lower().split())
    intents: list[str] = []
    if re.search(r"\b(how many|count|number of)\b", text):
        intents.append("aggregation")
    if re.search(r"\b(who|what|which)\b.*\b(manages?|owns?|supplies?|sponsors?|works? in|assigned|uses?)\b", text):
        intents.append("relationship_lookup")
    if sum(token in text for token in (" that ", " used by ", " connected ", " through ", " involve ")) or text.count(" which ") > 1:
        intents.append("multi_hop")
    if re.search(r"\b(describe|explain|tell me about|details)\b", text):
        intents.append("descriptive")
    if re.search(r"\b(who|what|which|where)\b", text) and not intents:
        intents.append("entity_lookup")
    return intents or ["unknown"]


def extract_entity_mentions(question: str) -> list[str]:
    """Extract title-like spans; retrieval also semantically searches the full question."""
    mentions = re.findall(r"\b(?:[A-Z][\w'-]*(?:\s+|$)){1,6}", question)
    stop = {"Which", "What", "Who", "Where", "How", "The"}
    cleaned = [" ".join(m.split()).rstrip("?.") for m in mentions]
    return list(dict.fromkeys(m for m in cleaned if m and m not in stop))

