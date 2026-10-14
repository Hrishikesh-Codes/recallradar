"""HTTP for ingesters: retries with backoff, a polite per-host request rate, and JSON helpers."""

import logging
import random
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger("recallradar.ingest.http")

USER_AGENT = "RecallRadar/0.1 (+https://github.com/Hrishikesh-Codes/recallradar)"
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 5
# openFDA allows 240 requests/minute; CPSC publishes no limit, so be gentle with it.
MIN_INTERVAL_S = {"api.fda.gov": 0.3, "www.saferproducts.gov": 1.0}

_last_request: dict[str, float] = {}


class NotFoundError(Exception):
    """HTTP 404: for openFDA this means "no records match"."""


def make_client(timeout: float = 120.0) -> httpx.Client:
    return httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def _throttle(url: str) -> None:
    host = urlsplit(url).hostname or ""
    wait = MIN_INTERVAL_S.get(host, 0.0) - (time.monotonic() - _last_request.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    _last_request[host] = time.monotonic()


def _request(client: httpx.Client, url: str, params: dict[str, Any] | None) -> httpx.Response:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        _throttle(url)
        try:
            response = client.get(url, params=params)
        except (httpx.TransportError, httpx.TimeoutException) as error:
            if attempt == MAX_ATTEMPTS:
                raise
            reason = repr(error)
        else:
            if response.status_code == 404:
                raise NotFoundError(str(response.url))
            if response.status_code not in RETRY_STATUS or attempt == MAX_ATTEMPTS:
                response.raise_for_status()
                return response
            reason = f"HTTP {response.status_code}"
            retry_after = response.headers.get("retry-after", "")
            if retry_after.isdigit():
                time.sleep(min(int(retry_after), 60))
        delay = min(2**attempt, 30) + random.uniform(0, 1)  # noqa: S311 - jitter, not crypto
        logger.warning("retrying", extra={"url": url, "attempt": attempt, "reason": reason})
        time.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


def get_json(client: httpx.Client, url: str, params: dict[str, Any] | None = None) -> Any:
    return _request(client, url, params).json()


def get_json_with_links(
    client: httpx.Client, url: str, params: dict[str, Any] | None = None
) -> tuple[Any, dict[str, str]]:
    """JSON body plus `Link` header URLs by rel ("next", ...)."""
    response = _request(client, url, params)
    links = {str(rel): link["url"] for rel, link in response.links.items() if rel and "url" in link}
    return response.json(), links
