import json

from app.ai.context.redactor import redact
from app.ai.context.selector import select_evidence
from app.errors import ServiceError


def build_context(context, settings):
    chosen = select_evidence(context.evidence, settings.max_evidence)
    data = context.model_dump(mode="json")
    data["evidence"] = [e.model_dump(mode="json") for e in chosen]
    # Redact before truncating: truncated PEM/credential text must never escape detection.
    data = redact(data)
    data["timeline"] = data["timeline"][-30:]
    data["summary"] = data["summary"][:2000]
    for item in data["evidence"]:
        item["summary"] = item["summary"][:2000]
    selected_count = len(chosen)
    while len(json.dumps(data, ensure_ascii=False)) > settings.max_context_chars:
        if data["timeline"]:
            data["timeline"].pop(0)
        elif data.get("telemetry"):
            data["telemetry"].pop()
            note = "host telemetry omitted to respect context budget: UNKNOWN"
            if note not in data["missing_telemetry"]:
                data["missing_telemetry"].append(note)
        elif data["evidence"]:
            data["evidence"].pop()
        else:
            raise ServiceError("context_metadata_exceeds_budget", 422)
    omitted = len(context.evidence) - len(data["evidence"])
    return {
        "classification": "UNTRUSTED EVENT DATA",
        "omitted_evidence_count": omitted,
        "selection_limit": selected_count,
        "data": data,
    }
