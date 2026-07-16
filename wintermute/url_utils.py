from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def canonicalize_url(raw_url: str) -> str:
    """Return the canonical storage form for an absolute HTTP(S) URL."""
    parts = urlsplit(raw_url.strip())
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("URL must be absolute HTTP or HTTPS")

    host = parts.hostname.lower()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = parts.port
    if port is not None and not (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    ):
        host = f"{host}:{port}"

    path = parts.path.rstrip("/") or "/"
    return urlunsplit((scheme, host, path, parts.query, ""))
