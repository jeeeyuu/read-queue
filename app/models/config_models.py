"""Configuration models for application and secret settings."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TelegramConfig(BaseModel):
    """Telegram bot behavior configuration."""

    mode: str = "polling"
    polling_interval_seconds: int = 3
    allowed_chat_ids: list[int] = Field(default_factory=list)


class OpenAIConfig(BaseModel):
    """OpenAI API runtime configuration."""

    model: str = "gpt-4.1-mini"
    language: str = "ko"
    max_input_chars: int = 4000


class NotionPropertyNames(BaseModel):
    """Configurable Notion database property names."""

    title: str = "Title"
    url: str = "URL"
    canonical_url: str = "Canonical URL"
    domain: str = "Domain"
    original_title: str = "Original Title"
    cleaned_title_ko: str = "Cleaned Title KO"
    summary_one_line_ko: str = "Summary One Line KO"
    status: str = "Status"
    read: str = "Read"
    note: str = "Note"
    tags: str = "Tags"
    source: str = "Source"
    saved_at: str = "Saved At"
    telegram_message_id: str = "Telegram Message ID"
    error_message: str = "Error Message"


class NotionConfig(BaseModel):
    """Notion API and database configuration."""

    database_id: str
    properties: NotionPropertyNames = Field(default_factory=NotionPropertyNames)


class DefaultsConfig(BaseModel):
    """Default values for created records."""

    source: str = "telegram"
    initial_status: str = "Inbox"
    fallback_status_on_failure: str = "Failed"


class DedupConfig(BaseModel):
    """Duplicate detection strategy."""

    use_canonical_url_first: bool = True
    strip_tracking_params: bool = True


class NetworkConfig(BaseModel):
    """HTTP timeout and retry settings."""

    timeout_seconds: int = 20
    max_retries: int = 3
    retry_backoff_seconds: int = 2


class AppConfig(BaseModel):
    """Top-level non-secret application settings."""

    app_name: str = "ReadQueue"
    environment: str = "dev"
    log_level: str = "INFO"
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    notion: NotionConfig
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    dedup: DedupConfig = Field(default_factory=DedupConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)


class SecretsConfig(BaseModel):
    """Secret settings loaded from secrets.yaml."""

    OPENAI_API_KEY: str
    TELEGRAM_BOT_TOKEN: str
    NOTION_API_KEY: str


class Settings(BaseModel):
    """Runtime settings composed of non-secret and secret config."""

    app: AppConfig
    secrets: SecretsConfig
