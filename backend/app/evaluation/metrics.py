import re
from collections import Counter


def tokens(text: str) -> list[str]: return re.findall(r"[\w'-]+", text.lower())


def exact_match(answer: str, expected: str) -> float: return float(" ".join(tokens(answer)) == " ".join(tokens(expected)))


def token_f1(answer: str, expected: str) -> float:
    predicted, gold = Counter(tokens(answer)), Counter(tokens(expected))
    overlap = sum((predicted & gold).values())
    if not predicted or not gold: return float(predicted == gold)
    precision, recall = overlap / sum(predicted.values()), overlap / sum(gold.values())
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def coverage(text: str, expected: list[str]) -> float:
    return sum(item.lower() in text.lower() for item in expected) / len(expected) if expected else 1.0


def entity_recall(retrieved: list[str], expected: list[str]) -> float: return coverage(" | ".join(retrieved), expected)


def graph_path_recall(facts: list[str], expected_path: list[str]) -> float:
    return coverage(" | ".join(facts), expected_path) if expected_path else 0.0


def evidence_precision(answer: str, evidence: list[str]) -> float:
    meaningful = [token for token in tokens(answer) if len(token) > 3]
    supported = sum(token in tokens(" ".join(evidence)) for token in meaningful)
    return supported / len(meaningful) if meaningful else 1.0


def unsupported_claim_heuristic(answer: str, evidence: list[str]) -> float:
    return round(1.0 - evidence_precision(answer, evidence), 4)
