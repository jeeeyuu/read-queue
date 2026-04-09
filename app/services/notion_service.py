"""Notion API service for duplicate checks and page creation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.models.config_models import NotionConfig
from app.models.notion_models import NotionItemPayload
from app.utils.http_utils import request_with_retry


class NotionService:
    """Wraps Notion database query/create/update operations."""

    NOTION_VERSION = "2022-06-28"

    def __init__(
        self,
        api_key: str,
        notion_config: NotionConfig,
        timeout_seconds: int = 20,
        max_retries: int = 3,
        retry_backoff_seconds: int = 2,
    ) -> None:
        self._api_key = api_key
        self._cfg = notion_config
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Notion-Version": self.NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _rich_text(self, value: str | None) -> dict[str, Any]:
        if not value:
            return {"rich_text": []}
        return {"rich_text": [{"type": "text", "text": {"content": value[:2000]}}]}

    def _title_prop(self, value: str) -> dict[str, Any]:
        return {"title": [{"type": "text", "text": {"content": value[:2000]}}]}

    def _url_prop(self, value: str | None) -> dict[str, Any]:
        return {"url": value or None}

    def _select_prop(self, value: str | None) -> dict[str, Any]:
        return {"select": {"name": value}} if value else {"select": None}

    def _checkbox_prop(self, value: bool) -> dict[str, Any]:
        return {"checkbox": bool(value)}

    def _multi_select_prop(self, values: list[str] | None) -> dict[str, Any]:
        items = [{"name": tag} for tag in (values or []) if tag]
        return {"multi_select": items}

    def _date_prop(self, iso_value: str | None = None) -> dict[str, Any]:
        if not iso_value:
            iso_value = datetime.now(timezone.utc).isoformat()
        return {"date": {"start": iso_value}}

    def query_by_url(self, normalized_url: str) -> str | None:
        """Find first page id where URL property exactly matches normalized_url."""

        props = self._cfg.properties
        payload = {
            "filter": {
                "or": [
                    {"property": props.canonical_url, "url": {"equals": normalized_url}},
                    {"property": props.url, "url": {"equals": normalized_url}},
                ]
            },
            "page_size": 1,
        }

        def _call() -> dict[str, Any]:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(
                    f"https://api.notion.com/v1/databases/{self._cfg.database_id}/query",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()

        body = request_with_retry(_call, self._max_retries, self._retry_backoff_seconds)

        results = body.get("results", [])
        if not results:
            return None
        return results[0].get("id")

    def update_missing_text_fields(self, page_id: str, payload: NotionItemPayload) -> None:
        """Best-effort update for missing text fields on duplicates."""

        props = self._cfg.properties
        data = {
            props.original_title: self._rich_text(payload.original_title),
            props.cleaned_title_ko: self._rich_text(payload.cleaned_title_ko),
            props.summary_one_line_ko: self._rich_text(payload.summary_one_line_ko),
            props.error_message: self._rich_text(payload.error_message),
        }

        def _call() -> None:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.patch(
                    f"https://api.notion.com/v1/pages/{page_id}",
                    headers=self._headers(),
                    json={"properties": data},
                )
                resp.raise_for_status()

        request_with_retry(_call, self._max_retries, self._retry_backoff_seconds)

    def create_item(self, payload: NotionItemPayload) -> str:
        """Create a Notion page in configured database and return page id."""

        props = self._cfg.properties
        notion_props = {
            props.title: self._title_prop(payload.title),
            props.url: self._url_prop(payload.url),
            props.canonical_url: self._url_prop(payload.canonical_url),
            props.domain: self._rich_text(payload.domain),
            props.original_title: self._rich_text(payload.original_title),
            props.cleaned_title_ko: self._rich_text(payload.cleaned_title_ko),
            props.summary_one_line_ko: self._rich_text(payload.summary_one_line_ko),
            props.status: self._select_prop(payload.status),
            props.read: self._checkbox_prop(payload.read),
            props.note: self._rich_text(payload.note),
            props.tags: self._multi_select_prop(payload.tags),
            props.source: self._select_prop(payload.source),
            props.saved_at: self._date_prop(payload.saved_at_iso),
            props.telegram_message_id: self._rich_text(payload.telegram_message_id),
            props.error_message: self._rich_text(payload.error_message),
        }

        body = {
            "parent": {"database_id": self._cfg.database_id},
            "properties": notion_props,
        }

        def _call() -> dict[str, Any]:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post("https://api.notion.com/v1/pages", headers=self._headers(), json=body)
                resp.raise_for_status()
                return resp.json()

        page = request_with_retry(_call, self._max_retries, self._retry_backoff_seconds)
        return page["id"]
