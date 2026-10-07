import json
import ssl
from urllib.parse import urlparse

import httpx

from app.errors import DependencyUnavailable


def http_client(url, token, settings, ca_file="", transport=None):
    parsed = urlparse(url)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise DependencyUnavailable("invalid_dependency_url")
    if parsed.scheme == "http":
        trusted = {x.strip().lower() for x in settings.trusted_http_hosts.split(",") if x.strip()}
        loopback = parsed.hostname in {"127.0.0.1", "::1", "localhost"}
        trusted_host = settings.app_env in {"development", "test"} and parsed.hostname.lower() in trusted
        if not settings.allow_insecure_http or not (loopback or trusted_host):
            raise DependencyUnavailable("https_required")
    try:
        verify = ssl.create_default_context(cafile=ca_file or None)
        return httpx.AsyncClient(
            base_url=url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {token}"} if token else {},
            verify=verify,
            timeout=settings.http_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )
    except (OSError, ValueError) as exc:
        raise DependencyUnavailable("invalid_dependency_tls_configuration") from exc


async def json_request(client, method, path, *, limit, **kwargs):
    try:
        async with client.stream(method, path.lstrip("/"), **kwargs) as response:
            if response.status_code == 404:
                return None
            response.raise_for_status()
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > limit:
                    raise DependencyUnavailable("dependency_response_too_large")
            return json.loads(body)
    except (httpx.HTTPError, ValueError) as exc:
        raise DependencyUnavailable() from exc
