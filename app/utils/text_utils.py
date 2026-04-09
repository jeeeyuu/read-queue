"""Text utility helpers."""

from __future__ import annotations


def truncate_text(value: str | None, limit: int) -> str:
    """Safely truncate text to API-safe input length."""

    if not value:
        return ""
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "…"
