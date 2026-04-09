"""Domain models used for Notion storage operations."""

from __future__ import annotations

from pydantic import BaseModel


class NotionItemPayload(BaseModel):
    """Internal representation of a reading item before Notion write."""

    title: str
    url: str
    canonical_url: str | None = None
    domain: str | None = None
    original_title: str | None = None
    cleaned_title_ko: str | None = None
    summary_one_line_ko: str | None = None
    status: str
    read: bool = False
    note: str | None = None
    tags: list[str] | None = None
    source: str
    saved_at_iso: str
    telegram_message_id: str
    error_message: str | None = None
