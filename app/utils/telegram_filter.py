"""Helpers for Telegram metadata normalization."""

from __future__ import annotations


def normalize_telegram_username(username: str) -> str:
    """Normalize username to lowercase @handle form."""

    value = (username or "").strip().lower()
    if not value:
        return ""
    if not value.startswith("@"):
        value = f"@{value}"
    return value
