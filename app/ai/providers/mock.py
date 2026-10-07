from app.ai.providers.base import AIProvider


class MockAIProvider(AIProvider):
    name, model = "mock", "deterministic-v1"

    async def analyze(self, context):
        data = context["data"]
        return {
            "observed_facts": [
                {"text": f"An event was recorded by {e['source']}.", "evidence_event_ids": [e["event_uid"]]}
                for e in data["evidence"]
            ],
            "hypotheses": [
                {
                    "text": "Activity requires analyst review.",
                    "limitations": "The deterministic mock makes no threat diagnosis; missing telemetry remains UNKNOWN.",
                }
            ],
            "missing_evidence": data["missing_telemetry"],
            "recommended_investigation": ["Review the cited events and obtain missing telemetry."],
            "containment_options": [
                "Consider containment only after an analyst proposal and independent operator approval."
            ],
        }
