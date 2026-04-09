"""Metadata fetch and extraction service for article URLs."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.utils.http_utils import request_with_retry
from app.utils.url_utils import domain_from_url

logger = logging.getLogger(__name__)


@dataclass
class MetadataResult:
    """Result object for metadata extraction."""

    requested_url: str
    final_url: str
    canonical_url: str | None
    domain: str
    original_title: str | None
    excerpt: str | None
    error: str | None = None

    @property
    def failed(self) -> bool:
        return self.error is not None


class MetadataService:
    """Fetches and parses page metadata from HTML."""

    def __init__(self, timeout_seconds: int = 20, max_retries: int = 3, retry_backoff_seconds: int = 2) -> None:
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds

    def fetch(self, url: str) -> MetadataResult:
        """Fetch HTML and parse metadata. Return fallback metadata on failure."""

        try:
            def _call() -> tuple[str, str]:
                with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                    resp = client.get(url, headers={"User-Agent": "read-queue-bot/0.1"})
                    resp.raise_for_status()
                    return str(resp.url), resp.text

            final_url, html = request_with_retry(
                _call,
                self._max_retries,
                self._retry_backoff_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            domain = domain_from_url(url)
            return MetadataResult(
                requested_url=url,
                final_url=url,
                canonical_url=None,
                domain=domain,
                original_title=None,
                excerpt=None,
                error=f"metadata fetch failed: {exc}",
            )

        try:
            soup = BeautifulSoup(html, "html.parser")
            title = (soup.title.string.strip() if soup.title and soup.title.string else None)

            canonical_tag = soup.find("link", attrs={"rel": lambda v: v and "canonical" in v})
            canonical_url = canonical_tag.get("href").strip() if canonical_tag and canonical_tag.get("href") else None
            if canonical_url:
                canonical_url = urljoin(final_url, canonical_url)

            excerpt = None
            for key, attr in (("description", "name"), ("og:description", "property")):
                tag = soup.find("meta", attrs={attr: key})
                if tag and tag.get("content"):
                    excerpt = tag["content"].strip()
                    break

            return MetadataResult(
                requested_url=url,
                final_url=final_url,
                canonical_url=canonical_url,
                domain=domain_from_url(final_url),
                original_title=title,
                excerpt=excerpt,
                error=None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("metadata parse failed")
            return MetadataResult(
                requested_url=url,
                final_url=final_url,
                canonical_url=None,
                domain=domain_from_url(final_url),
                original_title=None,
                excerpt=None,
                error=f"metadata parse failed: {exc}",
            )
