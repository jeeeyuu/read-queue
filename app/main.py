"""Main application orchestration for Telegram polling and shared ingestion."""

from __future__ import annotations

import logging
import time

from app.config import load_settings
from app.models.processing_models import ProcessingResult
from app.models.telegram_models import TelegramMessage, TelegramUpdate
from app.services.dedup_service import DedupService
from app.services.ingestion_service import IngestionService
from app.services.metadata_service import MetadataService
from app.services.notion_service import NotionService
from app.services.openai_service import OpenAIService
from app.services.telegram_service import TelegramService
from app.utils.telegram_filter import normalize_telegram_username

logger = logging.getLogger(__name__)


class ReadingInboxApp:
    """Coordinates integrations and routes input to shared ingestion service."""

    def __init__(self) -> None:
        self.settings = load_settings()
        cfg = self.settings.app

        self.telegram = TelegramService(
            bot_token=self.settings.secrets.TELEGRAM_BOT_TOKEN,
            timeout_seconds=cfg.network.timeout_seconds,
            max_retries=cfg.network.max_retries,
            retry_backoff_seconds=cfg.network.retry_backoff_seconds,
        )
        metadata = MetadataService(
            timeout_seconds=cfg.network.timeout_seconds,
            max_retries=cfg.network.max_retries,
            retry_backoff_seconds=cfg.network.retry_backoff_seconds,
        )
        openai = OpenAIService(
            api_key=self.settings.secrets.OPENAI_API_KEY,
            model=cfg.openai.model,
            language=cfg.openai.language,
            timeout_seconds=cfg.network.timeout_seconds,
            max_input_chars=cfg.openai.max_input_chars,
            max_retries=cfg.network.max_retries,
            retry_backoff_seconds=cfg.network.retry_backoff_seconds,
        )
        notion = NotionService(
            api_key=self.settings.secrets.NOTION_API_KEY,
            notion_config=cfg.notion,
            timeout_seconds=cfg.network.timeout_seconds,
            max_retries=cfg.network.max_retries,
            retry_backoff_seconds=cfg.network.retry_backoff_seconds,
        )
        dedup = DedupService(cfg.dedup)

        self.ingestion = IngestionService(
            app_config=cfg,
            notion=notion,
            metadata=metadata,
            openai=openai,
            dedup=dedup,
        )

    def _effective_allowed_chat_ids(self) -> set[int]:
        return set(self.settings.secrets.TELEGRAM_ALLOWED_CHAT_IDS)

    def _authorize_message(self, msg: TelegramMessage) -> tuple[bool, str]:
        """Authorize a Telegram message before any expensive pipeline work."""

        cfg = self.settings.app.telegram
        if cfg.private_chat_only and msg.chat_type != "private":
            return False, "non_private_chat"

        allowed_chat_ids = self._effective_allowed_chat_ids()
        if not allowed_chat_ids:
            return False, "default_deny_no_allowlist"

        if msg.chat_id in allowed_chat_ids:
            return True, "allowed_chat_id"

        return False, "not_in_allowed_chat_ids"

    def _build_telegram_source(self, sender_username: str | None) -> str:
        """Build Notion source label for Telegram input as telegram:username."""

        normalized = normalize_telegram_username(sender_username or "")
        username = normalized.lstrip("@") if normalized else "unknown"
        return f"telegram:{username}"

    def process_input_text(
        self,
        text: str,
        source: str,
        telegram_message_id: int | None = None,
    ) -> ProcessingResult:
        """Public shared ingestion entrypoint for any text source."""

        return self.ingestion.process_input_text(
            text=text,
            source=source,
            telegram_message_id=telegram_message_id,
        )

    def process_telegram_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        sender_username: str | None,
    ) -> None:
        """Process Telegram message via shared ingestion pipeline and reply."""

        source = self._build_telegram_source(sender_username)
        result = self.process_input_text(text=text, source=source, telegram_message_id=message_id)
        if result.url_count == 0:
            return

        for item in result.item_results:
            self.telegram.send_message(chat_id=chat_id, text=item.message)

    def _handle_updates_batch(self, updates: list[TelegramUpdate], last_update_id: int | None) -> tuple[int | None, int]:
        """Handle polled updates while always advancing offsets, even when ignored."""

        processed_count = 0
        next_offset = last_update_id

        for update in updates:
            next_offset = update.update_id + 1
            msg = update.message

            authorized, reason = self._authorize_message(msg)
            if not authorized:
                # Unauthorized updates are consumed by offset, then discarded immediately.
                continue

            self.process_telegram_message(
                chat_id=msg.chat_id,
                message_id=msg.message_id,
                text=msg.text,
                sender_username=msg.sender_username,
            )
            processed_count += 1

        return next_offset, processed_count

    def run_polling_forever(self) -> None:
        """Main polling loop for Telegram updates."""

        cfg = self.settings.app.telegram
        interval = cfg.polling_interval_seconds
        status_interval = max(60, cfg.status_log_interval_seconds)

        last_update_id: int | None = None
        next_heartbeat_at = time.monotonic() + status_interval

        while True:
            try:
                updates = self.telegram.poll_updates(offset=last_update_id, timeout=20)
                last_update_id, processed_count = self._handle_updates_batch(updates, last_update_id)

                if processed_count > 0:
                    logger.info(
                        "processed telegram updates",
                        extra={"extra": {"processed_count": processed_count}},
                    )

                now = time.monotonic()
                if now >= next_heartbeat_at:
                    logger.info(
                        "polling alive",
                        extra={
                            "extra": {
                                "status": "alive",
                                "interval_seconds": interval,
                                "status_log_interval_seconds": status_interval,
                            }
                        },
                    )
                    next_heartbeat_at = now + status_interval
            except Exception:  # noqa: BLE001
                logger.exception("polling loop error")
            time.sleep(interval)
