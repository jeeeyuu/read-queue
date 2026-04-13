from __future__ import annotations

import pytest

from app.main import ReadingInboxApp
from app.models.config_models import AppConfig, SecretsConfig, Settings
from app.models.telegram_models import TelegramMessage, TelegramUpdate


class FakeTelegram:
    def __init__(self, updates: list[TelegramUpdate]) -> None:
        self._updates = updates
        self.offset_calls: list[int | None] = []

    def poll_updates(self, offset: int | None = None, timeout: int = 20) -> list[TelegramUpdate]:
        self.offset_calls.append(offset)
        if offset is None:
            return self._updates
        raise KeyboardInterrupt

    def send_message(self, chat_id: int, text: str) -> None:
        return None


def _build_app(
    *,
    allowed_chat_ids_secret: list[int] | None = None,
    private_chat_only: bool = False,
) -> ReadingInboxApp:
    app_cfg = AppConfig.model_validate(
        {
            "app_name": "ReadQueue",
            "environment": "test",
            "log_level": "INFO",
            "telegram": {
                "polling_interval_seconds": 0,
                "status_log_interval_seconds": 3600,
                "private_chat_only": private_chat_only,
            },
            "openai": {},
            "notion": {"database_id": "db123", "properties": {}},
            "defaults": {},
            "dedup": {},
            "network": {},
            "local_input": {},
            "launchers": {"generate_windows_bat": False, "generate_macos_command": False},
            "linux_runtime": {},
        }
    )
    secrets_cfg = SecretsConfig.model_validate(
        {
            "OPENAI_API_KEY": "k1",
            "TELEGRAM_BOT_TOKEN": "k2",
            "NOTION_API_KEY": "k3",
            "TELEGRAM_ALLOWED_CHAT_IDS": allowed_chat_ids_secret or [],
        }
    )

    app = ReadingInboxApp.__new__(ReadingInboxApp)
    app.settings = Settings(app=app_cfg, secrets=secrets_cfg)
    app._last_unauthorized_log_at = {}
    app.telegram = FakeTelegram([])
    return app


def _msg(*, username: str | None, chat_id: int = 1, chat_type: str = "private") -> TelegramMessage:
    return TelegramMessage(
        message_id=10,
        chat_id=chat_id,
        chat_type=chat_type,
        text="https://example.com",
        sender_username=username,
    )




def test_default_deny_when_no_allowlist() -> None:
    app = _build_app()
    ok, reason = app._authorize_message(_msg(username="alice", chat_id=1))
    assert ok is False
    assert reason == "default_deny_no_allowlist"

def test_authorized_chat_id_from_secret_allowlist() -> None:
    app = _build_app(allowed_chat_ids_secret=[111])
    ok, reason = app._authorize_message(_msg(username="Alice", chat_id=111))
    assert ok is True
    assert reason == "allowed_chat_id"


def test_unauthorized_chat_id_when_allowlist_exists() -> None:
    app = _build_app(allowed_chat_ids_secret=[111])
    ok, reason = app._authorize_message(_msg(username="Alice", chat_id=222))
    assert ok is False
    assert reason == "not_in_allowed_chat_ids"


def test_allowed_chat_id_from_secret_allowlist_when_username_missing() -> None:
    app = _build_app(allowed_chat_ids_secret=[42])
    ok, reason = app._authorize_message(_msg(username=None, chat_id=42))
    assert ok is True
    assert reason == "allowed_chat_id"


def test_private_chat_only_blocks_non_private_chat() -> None:
    app = _build_app(allowed_chat_ids_secret=[999], private_chat_only=True)
    ok, reason = app._authorize_message(_msg(username="alice", chat_type="group", chat_id=999))
    assert ok is False
    assert reason == "non_private_chat"


def test_ignored_updates_still_advance_offset_and_not_reprocessed() -> None:
    app = _build_app(allowed_chat_ids_secret=[1001])

    updates = [
        TelegramUpdate(update_id=100, message=_msg(username="bob", chat_id=1000)),
        TelegramUpdate(update_id=101, message=_msg(username="alice", chat_id=1001)),
    ]
    fake = FakeTelegram(updates)
    app.telegram = fake

    processed: list[tuple[int, int, str | None]] = []
    app.process_telegram_message = (
        lambda chat_id, message_id, text, sender_username: processed.append((chat_id, message_id, sender_username))
    )

    with pytest.raises(KeyboardInterrupt):
        app.run_polling_forever()

    assert fake.offset_calls[0] is None
    assert fake.offset_calls[1] == 102
    assert processed == [(1001, 10, "alice")]


def test_source_format_is_telegram_username() -> None:
    app = _build_app()
    source = app._build_telegram_source("@Alice")
    assert source == "telegram:alice"
