"""
TLS 1.3-enforced httpx async client factory.

All outbound HTTP calls (bank APIs, tax authority, OCR) MUST use the client
returned by get_http_client() to ensure TLS 1.3 minimum is enforced.
"""

from __future__ import annotations

import ssl

import httpx


def _build_ssl_context() -> ssl.SSLContext:
    """Return an SSLContext that enforces TLS 1.3 as the minimum version."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_default_certs()
    return ctx


def get_http_client(**kwargs) -> httpx.AsyncClient:  # noqa: ANN003
    """Create an httpx.AsyncClient with TLS 1.3 enforced.

    Additional keyword arguments are forwarded to httpx.AsyncClient,
    allowing callers to set timeouts, headers, base_url, etc.

    Usage::

        async with get_http_client(timeout=10.0) as client:
            response = await client.get("https://api.bank.example/balance")

    Returns:
        A configured httpx.AsyncClient instance.
    """
    ssl_context = _build_ssl_context()
    return httpx.AsyncClient(verify=ssl_context, **kwargs)
