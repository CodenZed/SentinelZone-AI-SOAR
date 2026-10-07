from datetime import datetime, timezone


def utc(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, dict):
        return {k: utc(v) for k, v in value.items()}
    if isinstance(value, list):
        return [utc(v) for v in value]
    return value


def fields(row, names):
    return utc({k: getattr(row, k) for k in names})
