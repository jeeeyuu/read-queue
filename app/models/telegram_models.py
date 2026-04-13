"""Telegram API response and update models."""

from __future__ import annotations

from pydantic import BaseModel


class TelegramMessage(BaseModel):
    """Subset of Telegram message fields used by this app."""

    message_id: int
    chat_id: int
    chat_type: str = "private"
    text: str
    sender_username: str | None = None


class TelegramUpdate(BaseModel):
    """Incoming Telegram update in polling mode."""

    update_id: int
    message: TelegramMessage
