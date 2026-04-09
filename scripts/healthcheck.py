"""Simple local healthcheck for config and credentials."""

from __future__ import annotations

import sys

from app.config import ConfigError, load_settings
from app.services.notion_service import NotionService
from app.services.telegram_service import TelegramService


def main() -> None:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Config error: {exc}")
        sys.exit(1)

    telegram = TelegramService(
        settings.secrets.TELEGRAM_BOT_TOKEN,
        settings.app.network.timeout_seconds,
        settings.app.network.max_retries,
        settings.app.network.retry_backoff_seconds,
    )
    notion = NotionService(
        settings.secrets.NOTION_API_KEY,
        settings.app.notion,
        timeout_seconds=settings.app.network.timeout_seconds,
        max_retries=settings.app.network.max_retries,
        retry_backoff_seconds=settings.app.network.retry_backoff_seconds,
    )

    try:
        me = telegram.get_me()
        print(f"Telegram OK: @{me.get('username', 'unknown')}")
    except Exception as exc:  # noqa: BLE001
        print(f"Telegram check failed: {exc}")
        sys.exit(1)

    # Query with impossible URL to validate Notion API reachability and database access.
    try:
        notion.query_by_url("https://example.invalid/healthcheck")
        print("Notion OK: database reachable")
    except Exception as exc:  # noqa: BLE001
        print(f"Notion check failed: {exc}")
        sys.exit(1)

    print("Healthcheck passed")


if __name__ == "__main__":
    main()
