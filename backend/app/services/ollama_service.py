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
            "Do not copy the language of the evidence or conversation history when it differs from the current question. "
            "For a mixed-language question, use its dominant language while preserving names and technical terms."
        )
        payload = {"model": self.settings.ollama_model, "stream": False, "prompt": f"{system}\n\n{context}\n\nQuestion: {question}"}
        async with httpx.AsyncClient(timeout=self.settings.ollama_timeout_seconds) as client:
            response = await client.post(f"{self.settings.ollama_base_url}/api/generate", json=payload)
            response.raise_for_status()
            return str(response.json()["response"]).strip()
