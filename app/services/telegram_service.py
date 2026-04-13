"""Telegram Bot API polling and reply functions."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.models.telegram_models import TelegramMessage, TelegramUpdate
from app.utils.http_utils import request_with_retry

logger = logging.getLogger(__name__)


class TelegramService:
    """Small wrapper around Telegram Bot API for polling mode."""

    def __init__(
        self,
        bot_token: str,
        timeout_seconds: int = 20,
        max_retries: int = 3,
        retry_backoff_seconds: int = 2,
    ) -> None:
        self._base_url = f"https://api.telegram.org/bot{bot_token}"
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds

    def get_me(self) -> dict[str, Any]:
        """Validate token by calling getMe endpoint."""

        def _call() -> dict[str, Any]:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{self._base_url}/getMe")
                resp.raise_for_status()
                body = resp.json()
                if not body.get("ok"):
                    raise RuntimeError(f"Telegram getMe failed: {body}")
                return body.get("result", {})

        return request_with_retry(_call, self._max_retries, self._retry_backoff_seconds)

    def poll_updates(self, offset: int | None = None, timeout: int = 20) -> list[TelegramUpdate]:
        """Fetch updates using long-polling and parse text messages."""

        params: dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset

        def _call() -> dict[str, Any]:
            with httpx.Client(timeout=timeout + 5) as client:
                resp = client.get(f"{self._base_url}/getUpdates", params=params)
                resp.raise_for_status()
                return resp.json()

        body = request_with_retry(_call, self._max_retries, self._retry_backoff_seconds)

        if not body.get("ok"):
            logger.error("telegram.getUpdates returned not ok", extra={"extra": {"body": body}})
            return []

        updates: list[TelegramUpdate] = []
        for raw in body.get("result", []):
            message = raw.get("message") or {}
            text = message.get("text")
            if not text:
                continue

            chat = message.get("chat") or {}
            sender = message.get("from") or {}
            chat_id = chat.get("id")
            chat_type = chat.get("type") or "private"
            message_id = message.get("message_id")
            update_id = raw.get("update_id")
            sender_username = sender.get("username")
            if chat_id is None or message_id is None or update_id is None:
                continue

            updates.append(
                TelegramUpdate(
                    update_id=update_id,
                    message=TelegramMessage(
                        message_id=message_id,
                        chat_id=chat_id,
                        chat_type=chat_type,
                        text=text,
                        sender_username=sender_username,
                    ),
                )
            )
        return updates

    def send_message(self, chat_id: int, text: str) -> None:
        """Send concise response message to Telegram chat."""

        payload = {"chat_id": chat_id, "text": text}
        def _call() -> None:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(f"{self._base_url}/sendMessage", json=payload)
                resp.raise_for_status()

        request_with_retry(_call, self._max_retries, self._retry_backoff_seconds)
