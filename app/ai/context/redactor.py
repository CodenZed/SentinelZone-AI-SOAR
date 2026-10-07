import re
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

MASK = "[REDACTED]"
SENSITIVE_KEY = re.compile(
    r"password|passwd|passphrase|pwd|authorization|cookie|token|api.?key|secret|session.?id|private.?key|smtp.?credentials|credentials",
    re.I,
)
PEM = re.compile(r"-----BEGIN (?:[A-Z0-9 ]*PRIVATE KEY)-----.*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|$)", re.S)
URL_PASSWORD = re.compile(r"([a-z][a-z0-9+.-]*://[^\s/:@]+:)[^\s@/]+(@)", re.I)
JWT = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
AUTH = re.compile(r"(?im)(authorization\s*:\s*)(?:bearer|basic)\s+[^\s,;]+")
COOKIE = re.compile(r"(?im)((?:set-cookie|cookie)\s*:\s*)[^\r\n]+")
ASSIGNMENT = re.compile(
    r"""(?ix)((?:[\w.-]*(?:password|passwd|passphrase|pwd|token|api[ _-]?key|secret|session[ _-]?id|smtp[_-]?credentials)[\w.-]*)["']?\s*[:=]\s*)(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;&}\]]+)"""
)
KNOWN_TOKEN = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{12,}|AKIA[A-Z0-9]{16})\b")
QUOTED_HEADERS = re.compile(r"""(?ix)(["'](?:authorization|cookie|set-cookie)["']\s*:\s*)(?:"[^"\r\n]*"|'[^'\r\n]*')""")
SMTP_AUTH = re.compile(r"(?im)(\bAUTH\s+(?:PLAIN|LOGIN|XOAUTH2)\s+)[^\r\n]+")


URL = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^\s<>\"']+")


def redact_url(match):
    raw = match.group(0)
    try:
        parts = urlsplit(raw)
        # Redact query keys after decoding, including percent-encoded credential names.
        query = [
            (key, MASK if SENSITIVE_KEY.search(unquote(key)) else value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
        ]
        return urlunsplit(parts._replace(query=urlencode(query)))
    except ValueError:
        return MASK


def redact_text(value):
    value = PEM.sub(MASK, value)
    value = URL.sub(redact_url, value)
    value = QUOTED_HEADERS.sub(lambda m: m[1] + MASK, value)
    value = SMTP_AUTH.sub(r"\1[REDACTED]", value)
    value = URL_PASSWORD.sub(r"\1[REDACTED]\2", value)
    value = AUTH.sub(r"\1[REDACTED]", value)
    value = COOKIE.sub(r"\1[REDACTED]", value)
    value = ASSIGNMENT.sub(lambda m: m[1] + MASK, value)
    return KNOWN_TOKEN.sub(MASK, JWT.sub(MASK, value))


def redact(value):
    if isinstance(value, dict):
        return {redact_text(str(k)): MASK if SENSITIVE_KEY.search(str(k)) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
