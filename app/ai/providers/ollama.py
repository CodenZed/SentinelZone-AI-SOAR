"""Ollama native JSON-schema chat adapter. Live inference is a deployment gate."""

import json
from app.ai.providers.base import AIProvider, SYSTEM_PROMPT
from app.connectors.http import http_client, json_request
from app.contracts import AIOutput
from app.errors import DependencyUnavailable


class OllamaProvider(AIProvider):
    name = "ollama"

    def __init__(self, settings, transport=None):
        self.settings, self.model = settings, settings.ollama_model
        self.client = (
            http_client(settings.ollama_url, "", settings, transport=transport) if settings.ollama_url else None
        )

    async def analyze(self, context):
        if not self.client or not self.model:
            raise DependencyUnavailable("ai_provider_unconfigured")
        value = await json_request(
            self.client,
            "POST",
            "api/chat",
            limit=self.settings.max_response_bytes,
            timeout=self.settings.provider_timeout_seconds,
            json={
                "model": self.model,
                "stream": False,
                "think": False,
                "format": AIOutput.model_json_schema(),
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
                ],
                "options": {"temperature": 0, "num_predict": 6000},
            },
        )
        if not value or value.get("done") is not True or value.get("done_reason") not in {None, "stop"}:
            raise DependencyUnavailable("ai_response_incomplete")
        # Only structured content is returned; thinking/reasoning fields are never retained.
        return value["message"]["content"]

    async def health(self):
        if not self.client or not self.model:
            return "unavailable"
        value = await json_request(self.client, "GET", "api/tags", limit=self.settings.max_response_bytes)
        return (
            "healthy" if value and any(m.get("name") == self.model for m in value.get("models", [])) else "unavailable"
        )

    async def close(self):
        if self.client:
            await self.client.aclose()
