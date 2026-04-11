from __future__ import annotations

from app.models.config_models import AppConfig, DedupConfig
from app.services.dedup_service import DedupService
from app.services.ingestion_service import IngestionService
from app.services.metadata_service import MetadataResult


class FakeNotion:
    def __init__(self) -> None:
        self.created = []
        self.appended_notes: list[tuple[str, str]] = []

    def query_by_url(self, normalized_url: str) -> str | None:
        if "duplicate" in normalized_url:
            return "page-dup"
        return None

    def update_missing_text_fields(self, page_id: str, payload) -> None:
        return None

    def append_note_without_overwrite(self, page_id: str, note_to_append: str | None) -> None:
        if note_to_append:
            self.appended_notes.append((page_id, note_to_append))

    def create_item(self, payload) -> str:
        self.created.append(payload)
        return "page-new"


class FakeMetadata:
    def fetch(self, url: str) -> MetadataResult:
        return MetadataResult(
            requested_url=url,
            final_url=url,
            canonical_url=None,
            domain="example.com",
            original_title="Original",
            excerpt="Excerpt",
            error=None,
        )


class FailingMetadata:
    def fetch(self, url: str) -> MetadataResult:
        return MetadataResult(
            requested_url=url,
            final_url=url,
            canonical_url=None,
            domain="example.com",
            original_title=None,
            excerpt=None,
            error="metadata fetch failed",
        )


class FakeOpenAI:
    def summarize(self, url: str, original_title: str | None, excerpt: str | None):
        return "정리 제목", "한 줄 요약", None

    def summarize_from_text(self, url: str, input_text: str):
        return "메모 기반 제목", "메모 기반 한 줄 요약", None


class FailingFallbackOpenAI(FakeOpenAI):
    def summarize_from_text(self, url: str, input_text: str):
        return None, None, "fallback failed"


def _app_config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "app_name": "ReadQueue",
            "environment": "dev",
            "log_level": "INFO",
            "telegram": {},
            "openai": {},
            "notion": {"database_id": "db123", "properties": {}},
            "defaults": {"source": "telegram", "initial_status": "Inbox", "fallback_status_on_failure": "Failed"},
            "dedup": {},
            "network": {},
            "local_input": {"enabled": True, "source_name": "local", "os_mode": "auto"},
            "launchers": {"generate_windows_bat": False, "generate_macos_command": False},
            "linux_runtime": {},
        }
    )


def test_process_input_text_uses_local_source() -> None:
    notion = FakeNotion()
    svc = IngestionService(
        app_config=_app_config(),
        notion=notion,
        metadata=FakeMetadata(),
        openai=FakeOpenAI(),
        dedup=DedupService(DedupConfig(use_canonical_url_first=True, strip_tracking_params=True)),
    )

    result = svc.process_input_text("https://example.com/post", source="local")

    assert result.success_count == 1
    assert notion.created[0].source == "local"


def test_process_input_text_saves_non_url_text_to_note() -> None:
    notion = FakeNotion()
    svc = IngestionService(
        app_config=_app_config(),
        notion=notion,
        metadata=FakeMetadata(),
        openai=FakeOpenAI(),
        dedup=DedupService(DedupConfig(use_canonical_url_first=True, strip_tracking_params=True)),
    )

    svc.process_input_text("이건 링크 설명 메모 https://example.com/post", source="local")

    assert notion.created[0].note == "이건 링크 설명 메모"


def test_process_input_text_multiple_links_share_same_note() -> None:
    notion = FakeNotion()
    svc = IngestionService(
        app_config=_app_config(),
        notion=notion,
        metadata=FakeMetadata(),
        openai=FakeOpenAI(),
        dedup=DedupService(DedupConfig(use_canonical_url_first=True, strip_tracking_params=True)),
    )

    result = svc.process_input_text(
        "메모 텍스트 https://example.com/a 그리고 https://example.com/b",
        source="local",
    )

    assert result.success_count == 2
    assert len(notion.created) == 2
    assert notion.created[0].note == "메모 텍스트 그리고"
    assert notion.created[1].note == "메모 텍스트 그리고"


def test_process_input_text_dedups_same_link_in_one_input() -> None:
    notion = FakeNotion()
    svc = IngestionService(
        app_config=_app_config(),
        notion=notion,
        metadata=FakeMetadata(),
        openai=FakeOpenAI(),
        dedup=DedupService(DedupConfig(use_canonical_url_first=True, strip_tracking_params=True)),
    )

    result = svc.process_input_text(
        "https://example.com/a https://example.com/a",
        source="local",
    )

    assert result.success_count == 1
    assert result.duplicate_count == 1
    assert len(notion.created) == 1


def test_process_input_text_duplicate_appends_note() -> None:
    notion = FakeNotion()
    svc = IngestionService(
        app_config=_app_config(),
        notion=notion,
        metadata=FakeMetadata(),
        openai=FakeOpenAI(),
        dedup=DedupService(DedupConfig(use_canonical_url_first=True, strip_tracking_params=True)),
    )

    result = svc.process_input_text("추가 메모 https://example.com/duplicate", source="local")

    assert result.duplicate_count == 1
    assert notion.appended_notes == [("page-dup", "추가 메모")]


def test_metadata_failure_uses_note_fallback_summary() -> None:
    notion = FakeNotion()
    svc = IngestionService(
        app_config=_app_config(),
        notion=notion,
        metadata=FailingMetadata(),
        openai=FakeOpenAI(),
        dedup=DedupService(DedupConfig(use_canonical_url_first=True, strip_tracking_params=True)),
    )

    result = svc.process_input_text(
        "이 글은 AI 관련 링크 https://example.com/fail-meta",
        source="local",
    )

    assert result.success_count == 1
    assert notion.created[0].cleaned_title_ko == "메모 기반 제목"
    assert notion.created[0].summary_one_line_ko == "메모 기반 한 줄 요약"
    assert notion.created[0].error_message is None


def test_metadata_failure_and_fallback_failure_keeps_warning() -> None:
    notion = FakeNotion()
    svc = IngestionService(
        app_config=_app_config(),
        notion=notion,
        metadata=FailingMetadata(),
        openai=FailingFallbackOpenAI(),
        dedup=DedupService(DedupConfig(use_canonical_url_first=True, strip_tracking_params=True)),
    )

    result = svc.process_input_text(
        "메모 https://example.com/fail-meta",
        source="local",
    )

    assert result.warning_count == 1
    assert "fallback summarize failed" in (result.item_results[0].error or "")
