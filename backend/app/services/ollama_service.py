import re

import httpx

from app.config import Settings


class OllamaService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def health_check(self) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.settings.ollama_base_url}/api/tags")
                response.raise_for_status()
                names = [model.get("name") for model in response.json().get("models", [])]
                return {"healthy": True, "model_available": self.settings.ollama_model in names}
        except Exception as exc:
            return {"healthy": False, "model_available": False, "error": str(exc)}

    async def generate(self, question: str, context: str) -> str:
        system = (
            "Answer only from supplied evidence. If insufficient, explicitly say so. "
            "Never invent entities or relationships. Cite evidence identifiers in square brackets. "
            "Distinguish direct facts from conclusions and briefly explain relevant paths. "
            "Detect the language of the CURRENT question and answer entirely in that same language. "
            "Never append a translation or a second-language version of the answer. "
            "Do not copy the language of the evidence or conversation history when it differs from the current question. "
            "For a mixed-language question, use its dominant language while preserving names and technical terms. "
            "CRITICAL ENTITY IDENTITY RULE: the same label on different URIs means different, "
            "ambiguous records, never one person with multiple relationships. State how many "
            "distinct records share the label, enumerate their evidenced alternatives, and say "
            "that a unique answer requires an identifier or another distinguishing attribute. "
            "Never phrase multiple records as one person working in multiple departments."
        )
        if _contains_arabic(question):
            system += (
                " أجب باللغة العربية فقط. لا تستخدم الصينية أو الروسية أو أي ترجمة بلغة أخرى."
            )
        payload = {
            "model": self.settings.ollama_model,
            "stream": False,
            "system": system,
            "prompt": f"Evidence:\n{context}\n\nCurrent question: {question}",
            "options": {"temperature": 0.0, "seed": 42},
        }
        async with httpx.AsyncClient(timeout=self.settings.ollama_timeout_seconds) as client:
            response = await client.post(f"{self.settings.ollama_base_url}/api/generate", json=payload)
            response.raise_for_status()
            answer = str(response.json()["response"]).strip()
            if _arabic_question_with_foreign_script(question, answer):
                payload["system"] = (
                    system
                    + " The previous response violated the language rule. Respond in Arabic only. "
                    "أعد الإجابة كاملة باللغة العربية فقط، دون ترجمة أو حروف أجنبية."
                )
                response = await client.post(f"{self.settings.ollama_base_url}/api/generate", json=payload)
                response.raise_for_status()
                answer = str(response.json()["response"]).strip()
            return _remove_foreign_script_fragments(answer) if _contains_arabic(question) else answer


def _contains_arabic(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06ff]", text))


def _arabic_question_with_foreign_script(question: str, answer: str) -> bool:
    foreign_scripts = r"[\u0400-\u052f\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]"
    return _contains_arabic(question) and bool(re.search(foreign_scripts, answer))


def _remove_foreign_script_fragments(answer: str) -> str:
    """Final deterministic guard against an unwanted translated paragraph."""
    lines = [
        line for line in answer.splitlines()
        if not re.search(r"[\u0400-\u052f\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", line)
    ]
    return "\n".join(lines).strip()
