"""Main application orchestration for Telegram -> Notion ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import time

from app.config import load_settings
from app.models.notion_models import NotionItemPayload
from app.services.dedup_service import DedupService
from app.services.metadata_service import MetadataService
from app.services.notion_service import NotionService
from app.services.openai_service import OpenAIService
from app.services.telegram_service import TelegramService
from app.utils.url_utils import extract_urls, normalize_url

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    """Per-URL processing result for Telegram reply."""

    url: str
    status: str
    message: str


class ReadingInboxApp:
    """Coordinates parsing, dedup, metadata, summarization, and Notion writes."""

    def __init__(self) -> None:
        self.settings = load_settings()
        cfg = self.settings.app

        self.telegram = TelegramService(
            bot_token=self.settings.secrets.TELEGRAM_BOT_TOKEN,
            timeout_seconds=cfg.network.timeout_seconds,
            max_retries=cfg.network.max_retries,
            retry_backoff_seconds=cfg.network.retry_backoff_seconds,
        )
        self.metadata = MetadataService(
            timeout_seconds=cfg.network.timeout_seconds,
            max_retries=cfg.network.max_retries,
            retry_backoff_seconds=cfg.network.retry_backoff_seconds,
        )
        self.openai = OpenAIService(
            api_key=self.settings.secrets.OPENAI_API_KEY,
            model=cfg.openai.model,
            language=cfg.openai.language,
            timeout_seconds=cfg.network.timeout_seconds,
            max_input_chars=cfg.openai.max_input_chars,
            max_retries=cfg.network.max_retries,
            retry_backoff_seconds=cfg.network.retry_backoff_seconds,
        )
        self.notion = NotionService(
            api_key=self.settings.secrets.NOTION_API_KEY,
            notion_config=cfg.notion,
            timeout_seconds=cfg.network.timeout_seconds,
            max_retries=cfg.network.max_retries,
            retry_backoff_seconds=cfg.network.retry_backoff_seconds,
        )
        self.dedup = DedupService(cfg.dedup)

    def _is_allowed_chat(self, chat_id: int) -> bool:
        allowed = self.settings.app.telegram.allowed_chat_ids
        return not allowed or chat_id in allowed

    def _build_payload(
        self,
        url: str,
        canonical_url: str | None,
        domain: str,
        original_title: str | None,
        cleaned_title_ko: str | None,
        summary_one_line_ko: str | None,
        telegram_message_id: int,
        error_message: str | None,
    ) -> NotionItemPayload:
        defaults = self.settings.app.defaults

        has_warning = bool(error_message)
        status = defaults.fallback_status_on_failure if has_warning else defaults.initial_status

        effective_title = cleaned_title_ko or original_title or domain or url

        return NotionItemPayload(
            title=effective_title,
            url=url,
            canonical_url=canonical_url,
            domain=domain,
            original_title=original_title,
            cleaned_title_ko=cleaned_title_ko,
            summary_one_line_ko=summary_one_line_ko,
            status=status,
            read=False,
            note=None,
            tags=[],
            source=defaults.source,
            saved_at_iso=datetime.now(timezone.utc).isoformat(),
            telegram_message_id=str(telegram_message_id),
            error_message=error_message,
        )

    def process_url(self, url: str, telegram_message_id: int) -> ProcessResult:
        """Process a single URL and save it to Notion unless duplicate."""

        strip_tracking = self.settings.app.dedup.strip_tracking_params
        normalized_original = normalize_url(url, strip_tracking=strip_tracking)

        # Early duplicate check using normalized original URL.
        dup_page = self.notion.query_by_url(normalized_original)
        if dup_page:
            return ProcessResult(url=url, status="duplicate", message="Already exists in reading inbox.")

        metadata = self.metadata.fetch(normalized_original)
        normalized_canonical = (
            normalize_url(metadata.canonical_url, strip_tracking=strip_tracking)
            if metadata.canonical_url
            else None
        )

        for candidate in self.dedup.candidate_urls(normalized_original, normalized_canonical):
            dup_page = self.notion.query_by_url(candidate)
            if dup_page:
                payload = self._build_payload(
                    url=normalized_original,
                    canonical_url=normalized_canonical,
                    domain=metadata.domain,
                    original_title=metadata.original_title,
                    cleaned_title_ko=None,
                    summary_one_line_ko=None,
                    telegram_message_id=telegram_message_id,
                    error_message=metadata.error,
                )
                # Best-effort metadata backfill for existing record.
                try:
                    self.notion.update_missing_text_fields(dup_page, payload)
                except Exception:  # noqa: BLE001
                    logger.exception("failed to update duplicate with missing metadata")
                return ProcessResult(url=url, status="duplicate", message="Already exists in reading inbox.")

        cleaned_title = None
        summary_one_line = None
        warning = metadata.error

        if not metadata.failed:
            cleaned_title, summary_one_line, summarize_error = self.openai.summarize(
                url=metadata.final_url,
                original_title=metadata.original_title,
                excerpt=metadata.excerpt,
            )
            if summarize_error:
                warning = summarize_error

        payload = self._build_payload(
            url=normalized_original,
            canonical_url=normalized_canonical,
            domain=metadata.domain,
            original_title=metadata.original_title,
            cleaned_title_ko=cleaned_title,
            summary_one_line_ko=summary_one_line,
            telegram_message_id=telegram_message_id,
            error_message=warning,
        )
        self.notion.create_item(payload)

        if warning:
            return ProcessResult(
                url=url,
                status="warning",
                message="Saved with warning: metadata or summary failed.",
            )

        display_title = cleaned_title or metadata.original_title or metadata.domain
        return ProcessResult(url=url, status="success", message=f"Saved to Notion: {display_title}")

    def process_message(self, chat_id: int, message_id: int, text: str) -> None:
        """Extract and process all links in a Telegram message, then reply concisely."""

        urls = extract_urls(text)
        if not urls:
            return

        for raw_url in urls:
            try:
                result = self.process_url(raw_url, telegram_message_id=message_id)
                self.telegram.send_message(chat_id=chat_id, text=result.message)
            except Exception as exc:  # noqa: BLE001
                logger.exception("url processing failed")
                self.telegram.send_message(
                    chat_id=chat_id,
                    text="Saved with warning: metadata or summary failed.",
                )
                logger.error("process_url failed", extra={"extra": {"url": raw_url, "error": str(exc)}})

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
                    self.process_message(msg.chat_id, msg.message_id, msg.text)
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
