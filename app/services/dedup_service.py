"""Duplicate detection strategy helpers."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.config_models import DedupConfig


@dataclass
class DuplicateCheckResult:
    """Duplicate check result."""

    is_duplicate: bool
    duplicate_page_id: str | None = None


class DedupService:
    """Computes candidate URL keys and performs Notion duplicate checks."""

    def __init__(self, config: DedupConfig) -> None:
        self._cfg = config

    def candidate_urls(self, normalized_original: str, normalized_canonical: str | None) -> list[str]:
        """Return prioritized unique URL keys for duplicate lookup."""

        first = normalized_canonical if self._cfg.use_canonical_url_first else normalized_original
        second = normalized_original if self._cfg.use_canonical_url_first else normalized_canonical

        out: list[str] = []
        for value in (first, second):
            if value and value not in out:
                out.append(value)
        return out
