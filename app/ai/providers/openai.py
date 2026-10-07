import json

from app.ai.providers.base import AIProvider, SYSTEM_PROMPT
from app.connectors.http import http_client, json_request
from app.contracts import AIOutput
from app.errors import DependencyUnavailable


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self, settings, transport=None):
        self.settings, self.model = settings, settings.openai_model
        self.configured = bool(settings.openai_api_key and self.model)
        self.client = http_client(settings.openai_api_url, settings.openai_api_key, settings, transport=transport)

    async def analyze(self, context):
        if not self.configured:
            raise DependencyUnavailable("ai_provider_unconfigured")
        body = {
            "model": self.model,
            "store": False,
            "instructions": SYSTEM_PROMPT,
            "input": [{"role": "user", "content": json.dumps(context, ensure_ascii=False)}],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "incident_analysis",
                    "strict": True,
                    "schema": AIOutput.model_json_schema(),
                }
            },
            "max_output_tokens": 6000,
        }
        value = await json_request(
            self.client,
            "POST",
            "responses",
            limit=self.settings.max_response_bytes,
            json=body,
            timeout=self.settings.provider_timeout_seconds,
        )
        if not value or value.get("status") != "completed":
            raise DependencyUnavailable("ai_response_incomplete")
        texts = []
        for item in value.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "refusal":
                    raise DependencyUnavailable("ai_refused")
                if content.get("type") == "output_text":
                    texts.append(content["text"])
        if len(texts) != 1:
            raise DependencyUnavailable("ai_response_incomplete")
        return texts[0]

    async def health(self):
        if not self.configured:
            return "unavailable"
        result = await json_request(self.client, "GET", "models", limit=self.settings.max_response_bytes)
        return "healthy" if result and any(m.get("id") == self.model for m in result.get("data", [])) else "unavailable"

    async def close(self):
        await self.client.aclose()
