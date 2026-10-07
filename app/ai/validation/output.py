import json

from app.contracts import AIOutput


def parse_output(value):
    if isinstance(value, str):
        if len(value) > 100000:
            raise ValueError("AI output too large")

        def unique(pairs):
            result = {}
            for k, v in pairs:
                if k in result:
                    raise ValueError("duplicate JSON key")
                result[k] = v
            return result

        value = json.loads(value, object_pairs_hook=unique)
    return AIOutput.model_validate(value, strict=True)
