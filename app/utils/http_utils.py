"""HTTP retry/backoff helpers for transient external API failures."""

from __future__ import annotations

import time
from typing import Callable, TypeVar

import httpx

T = TypeVar("T")


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code < 600


def request_with_retry(
    call: Callable[[], T],
    max_retries: int,
    backoff_seconds: int,
) -> T:
    """Run an HTTP call with simple linear backoff for retryable failures."""

    attempt = 0
    while True:
        try:
            return call()
        except httpx.HTTPStatusError as exc:
            if attempt >= max_retries or not _is_retryable_status(exc.response.status_code):
                raise
        except (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError):
            if attempt >= max_retries:
                raise

        attempt += 1
        time.sleep(backoff_seconds * attempt)

