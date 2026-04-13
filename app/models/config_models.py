"""Configuration models for application and secret settings."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

class TelegramConfig(BaseModel):
    """Telegram bot behavior configuration."""

    mode: str = "polling"
    polling_interval_seconds: int = 3
    status_log_interval_seconds: int = 600
    private_chat_only: bool = False


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


class LocalInputConfig(BaseModel):
    """Settings for one-click local clipboard ingestion."""

    enabled: bool = True
    source_name: str = "local"
    os_mode: str = "auto"


class LaunchersConfig(BaseModel):
    """Settings for generating platform launcher wrappers."""

    generate_windows_bat: bool = False
    windows_bat_output_path: str = ""
    windows_pause_on_exit: bool = True
    generate_macos_command: bool = False
    macos_command_output_path: str = ""


class LinuxRuntimeConfig(BaseModel):
    """Linux/WSL runtime assumptions used by generated launchers."""

    project_root: str = ""
    run_root: str = ""
    python_bin: str = "python3"
    use_venv: bool = True
    venv_path: str = ".venv"


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
    local_input: LocalInputConfig = Field(default_factory=LocalInputConfig)
    launchers: LaunchersConfig = Field(default_factory=LaunchersConfig)
    linux_runtime: LinuxRuntimeConfig = Field(default_factory=LinuxRuntimeConfig)

    @model_validator(mode="after")
    def validate_launcher_paths(self) -> "AppConfig":
        if self.launchers.generate_windows_bat and not self.launchers.windows_bat_output_path:
            raise ValueError("launchers.windows_bat_output_path is required when generate_windows_bat=true")
        if self.launchers.generate_macos_command and not self.launchers.macos_command_output_path:
            raise ValueError("launchers.macos_command_output_path is required when generate_macos_command=true")

        if (self.launchers.generate_windows_bat or self.launchers.generate_macos_command) and not self.linux_runtime.run_root:
            raise ValueError("linux_runtime.run_root is required when launcher generation is enabled")
        return self


class SecretsConfig(BaseModel):
    """Secret settings loaded from secrets.yaml."""

    OPENAI_API_KEY: str
    TELEGRAM_BOT_TOKEN: str
    NOTION_API_KEY: str
    TELEGRAM_ALLOWED_CHAT_IDS: list[int] = Field(default_factory=list)


class Settings(BaseModel):
    """Runtime settings composed of non-secret and secret config."""

    app: AppConfig
    secrets: SecretsConfig
