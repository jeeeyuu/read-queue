"""Shared ingestion pipeline for Telegram and local clipboard inputs."""

from __future__ import annotations

from datetime import datetime, timezone
import logging

from app.models.config_models import AppConfig
from app.models.notion_models import NotionItemPayload
from app.models.processing_models import ProcessingItemResult, ProcessingResult
from app.services.dedup_service import DedupService
from app.services.metadata_service import MetadataResult, MetadataService
from app.services.notion_service import NotionService
from app.services.openai_service import OpenAIService
from app.utils.url_utils import extract_non_url_text, extract_urls, normalize_url

logger = logging.getLogger(__name__)

FAIL_MESSAGE = "Saved with warning: metadata or summary failed."
DUPLICATE_MESSAGE = "Already exists in reading inbox."


class IngestionService:
    """Runs full link ingestion flow and returns structured results."""

    def __init__(
        self,
        app_config: AppConfig,
        notion: NotionService,
        metadata: MetadataService,
        openai: OpenAIService,
        dedup: DedupService,
    ) -> None:
        self._cfg = app_config
        self._notion = notion
        self._metadata = metadata
        self._openai = openai
        self._dedup = dedup

    def _build_payload(
        self,
        *,
        source: str,
        note: str | None,
        url: str,
        canonical_url: str | None,
        domain: str,
        original_title: str | None,
        cleaned_title_ko: str | None,
        summary_one_line_ko: str | None,
        telegram_message_id: int | None,
        error_message: str | None,
    ) -> NotionItemPayload:
        defaults = self._cfg.defaults
        status = defaults.fallback_status_on_failure if error_message else defaults.initial_status

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
            note=note,
            tags=[],
            source=source or defaults.source,
            saved_at_iso=datetime.now(timezone.utc).isoformat(),
            telegram_message_id=str(telegram_message_id or ""),
            error_message=error_message,
        )

    def _check_duplicate(
        self,
        normalized_original: str,
        normalized_canonical: str | None,
        metadata: MetadataResult,
        telegram_message_id: int | None,
        source: str,
        note: str | None,
    ) -> ProcessingItemResult | None:
        for candidate in self._dedup.candidate_urls(normalized_original, normalized_canonical):
            dup_page = self._notion.query_by_url(candidate)
            if not dup_page:
                continue

            payload = self._build_payload(
                source=source,
                note=note,
                url=normalized_original,
                canonical_url=normalized_canonical,
                domain=metadata.domain,
                original_title=metadata.original_title,
                cleaned_title_ko=None,
                summary_one_line_ko=None,
                telegram_message_id=telegram_message_id,
                error_message=metadata.error,
            )
            try:
                self._notion.update_missing_text_fields(dup_page, payload)
            except Exception:  # noqa: BLE001
                logger.exception("failed to update duplicate with missing metadata")

            return ProcessingItemResult(
                url=normalized_original,
                status="duplicate",
                message=DUPLICATE_MESSAGE,
            )
        return None

    def _process_single_url(
        self,
        raw_url: str,
        source: str,
        note: str | None,
        telegram_message_id: int | None,
    ) -> ProcessingItemResult:
        strip_tracking = self._cfg.dedup.strip_tracking_params
        normalized_original = normalize_url(raw_url, strip_tracking=strip_tracking)

        try:
            early_dup = self._notion.query_by_url(normalized_original)
            if early_dup:
                return ProcessingItemResult(
                    url=normalized_original,
                    status="duplicate",
                    message=DUPLICATE_MESSAGE,
                )

            metadata = self._metadata.fetch(normalized_original)
            normalized_canonical = (
                normalize_url(metadata.canonical_url, strip_tracking=strip_tracking)
                if metadata.canonical_url
                else None
            )

            duplicate = self._check_duplicate(
                normalized_original,
                normalized_canonical,
                metadata,
                telegram_message_id,
                source,
                note,
            )
            if duplicate:
                return duplicate

            cleaned_title = None
            summary_one_line = None
            warning = metadata.error

            if not metadata.failed:
                cleaned_title, summary_one_line, summarize_error = self._openai.summarize(
                    url=metadata.final_url,
                    original_title=metadata.original_title,
                    excerpt=metadata.excerpt,
                )
                if summarize_error:
                    warning = summarize_error

            payload = self._build_payload(
                source=source,
                note=note,
                url=normalized_original,
                canonical_url=normalized_canonical,
                domain=metadata.domain,
                original_title=metadata.original_title,
                cleaned_title_ko=cleaned_title,
                summary_one_line_ko=summary_one_line,
                telegram_message_id=telegram_message_id,
                error_message=warning,
            )
            self._notion.create_item(payload)

            if warning:
                return ProcessingItemResult(
                    url=normalized_original,
                    status="warning",
                    message=FAIL_MESSAGE,
                    error=warning,
                )

            title = cleaned_title or metadata.original_title or metadata.domain
            return ProcessingItemResult(
                url=normalized_original,
                status="success",
                message=f"Saved to Notion: {title}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("failed to process url")
            return ProcessingItemResult(
                url=normalized_original,
                status="failure",
                message=FAIL_MESSAGE,
                error=str(exc),
            )

    def process_input_text(
        self,
        text: str,
        source: str,
        telegram_message_id: int | None = None,
    ) -> ProcessingResult:
        """Process all URLs in input text using shared ingestion flow.

        For multi-link input, links are processed independently in message order.
        If duplicated links appear in the same input, only the first one is processed,
        and the rest are marked as duplicate.
        """

        urls = extract_urls(text)
        if not urls:
            return ProcessingResult(source=source, input_text=text, item_results=[])

        note_text = extract_non_url_text(text) or None
        strip_tracking = self._cfg.dedup.strip_tracking_params

        results: list[ProcessingItemResult] = []
        seen_normalized: set[str] = set()

        for raw_url in urls:
            normalized = normalize_url(raw_url, strip_tracking=strip_tracking)
            if normalized in seen_normalized:
                results.append(
                    ProcessingItemResult(
                        url=normalized,
                        status="duplicate",
                        message=DUPLICATE_MESSAGE,
                        error="duplicate url in same input",
                    )
                )
                continue

            seen_normalized.add(normalized)
            results.append(
                self._process_single_url(
                    raw_url=raw_url,
                    source=source,
                    note=note_text,
                    telegram_message_id=telegram_message_id,
                )
            )

        return ProcessingResult(source=source, input_text=text, item_results=results)
