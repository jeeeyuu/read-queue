"""Main application orchestration for Telegram polling and shared ingestion."""

from __future__ import annotations

import logging
import time

from app.config import load_settings
from app.models.processing_models import ProcessingResult
from app.services.dedup_service import DedupService
from app.services.ingestion_service import IngestionService
from app.services.metadata_service import MetadataService
from app.services.notion_service import NotionService
from app.services.openai_service import OpenAIService
from app.services.telegram_service import TelegramService

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

    def _is_allowed_chat(self, chat_id: int) -> bool:
        allowed = self.settings.app.telegram.allowed_chat_ids
        return not allowed or chat_id in allowed

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

    def process_telegram_message(self, chat_id: int, message_id: int, text: str) -> None:
        """Process Telegram message via shared ingestion pipeline and reply."""

        result = self.process_input_text(text=text, source="telegram", telegram_message_id=message_id)
        if result.url_count == 0:
            return

        for item in result.item_results:
            self.telegram.send_message(chat_id=chat_id, text=item.message)

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
                processed_count = 0

                for update in updates:
                    last_update_id = update.update_id + 1
                    msg = update.message
                    if not self._is_allowed_chat(msg.chat_id):
                        continue
                    self.process_telegram_message(msg.chat_id, msg.message_id, msg.text)
                    processed_count += 1

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
