import json

from app.ai.providers.base import AIProvider, SYSTEM_PROMPT
from app.connectors.http import http_client, json_request
from app.contracts import AIOutput
from app.errors import DependencyUnavailable


class LocalModelProvider(AIProvider):
    """An OpenAI-compatible /v1/chat/completions endpoint, e.g. a local model server."""

    name = "local"

    def __init__(self, settings, transport=None):
        self.settings, self.model = settings, settings.local_ai_model
        self.client = (
            http_client(
                settings.local_ai_url, settings.local_ai_token, settings, settings.local_ai_ca_file, transport=transport
            )
            if settings.local_ai_url
            else None
        )

    async def analyze(self, context):
        if not self.client or not self.model:
            raise DependencyUnavailable("ai_provider_unconfigured")
        value = await json_request(
            self.client,
            "POST",
            "chat/completions",
            limit=self.settings.max_response_bytes,
            timeout=self.settings.provider_timeout_seconds,
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "incident_analysis",
                        "strict": True,
                        "schema": AIOutput.model_json_schema(),
                    },
                },
                "stream": False,
            },
        )
        choices = value.get("choices", []) if value else []
        if not choices or choices[0].get("finish_reason") != "stop" or choices[0]["message"].get("refusal"):
            raise DependencyUnavailable("ai_response_incomplete")
        return choices[0]["message"]["content"]

    async def health(self):
        if not self.client or not self.model:
            return "unavailable"
        value = await json_request(self.client, "GET", "models", limit=self.settings.max_response_bytes)
        return "healthy" if value and any(m.get("id") == self.model for m in value.get("data", [])) else "unavailable"

    async def close(self):
        if self.client:
            await self.client.aclose()
