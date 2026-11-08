"""Shared HTTP helper for external data sources.

Every ingestion fetch goes through :func:`get_with_retries` so that timeouts,
retry/backoff and the User-Agent are consistent across providers. Retries are
limited to failures that are plausibly transient (timeouts, connection errors,
HTTP 429 and 5xx); a 4xx means the request itself is wrong and is raised
immediately.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Mapping

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "wcip-data-sync/1.0 (+https://github.com/SMLG120/World-Cup-Intelligence-Platform)"
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER_SECONDS = 60.0


def get_with_retries(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: httpx.Timeout | float = DEFAULT_TIMEOUT,
    attempts: int = 3,
    backoff_base: float = 2.0,
    sleep=time.sleep,
) -> httpx.Response:
    """GET ``url`` with exponential backoff; return the successful response.

    Raises the last ``httpx`` error when every attempt fails.
    """

    merged_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = httpx.get(
                url,
                params=params,
                headers=merged_headers,
                timeout=timeout,
                follow_redirects=True,
            )
            if response.status_code in RETRYABLE_STATUS and attempt < attempts:
                delay = _retry_after(response) or backoff_base ** (attempt - 1)
                logger.warning(
                    "GET %s returned %s; retrying in %.1fs (attempt %d/%d)",
                    url, response.status_code, delay, attempt, attempts,
                )
                sleep(delay)
                continue
            response.raise_for_status()
            return response
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            delay = backoff_base ** (attempt - 1)
            logger.warning(
                "GET %s failed (%s); retrying in %.1fs (attempt %d/%d)",
                url, type(exc).__name__, delay, attempt, attempts,
            )
            sleep(delay)
    assert last_exc is not None
    raise last_exc


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return min(float(value), MAX_RETRY_AFTER_SECONDS)
    except ValueError:
        return None
