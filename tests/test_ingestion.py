from __future__ import annotations

from app.models.config_models import AppConfig, DedupConfig
from app.services.dedup_service import DedupService
from app.services.ingestion_service import IngestionService
from app.services.metadata_service import MetadataResult


class FakeNotion:
    def __init__(self) -> None:
        self.created = []

    def query_by_url(self, normalized_url: str) -> str | None:
        if "duplicate" in normalized_url:
            return "page-dup"
        return None

    def update_missing_text_fields(self, page_id: str, payload) -> None:
        return None

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


class FakeOpenAI:
    def summarize(self, url: str, original_title: str | None, excerpt: str | None):
        return "정리 제목", "한 줄 요약", None


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


def test_process_input_text_duplicate() -> None:
    notion = FakeNotion()
    svc = IngestionService(
        app_config=_app_config(),
        notion=notion,
        metadata=FakeMetadata(),
        openai=FakeOpenAI(),
        dedup=DedupService(DedupConfig(use_canonical_url_first=True, strip_tracking_params=True)),
    )

    result = svc.process_input_text("https://example.com/duplicate", source="local")

    assert result.duplicate_count == 1
    assert result.success_count == 0
