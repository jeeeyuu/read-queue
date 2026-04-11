from __future__ import annotations

from pathlib import Path

import pytest

from app.config import ConfigError, load_settings


CONFIG_YAML = """
app_name: "ReadQueue"
environment: "dev"
log_level: "INFO"
telegram:
  mode: "polling"
  polling_interval_seconds: 3
  status_log_interval_seconds: 600
  allowed_chat_ids: []
openai:
  model: "gpt-4.1-mini"
  language: "ko"
  max_input_chars: 4000
notion:
  database_id: "db123"
  properties: {}
defaults: {}
dedup: {}
network: {}
local_input: {}
launchers:
  generate_windows_bat: false
  windows_bat_output_path: ""
  generate_macos_command: false
  macos_command_output_path: ""
linux_runtime: {}
"""

BAD_LAUNCHER_CONFIG_YAML = """
app_name: "ReadQueue"
environment: "dev"
log_level: "INFO"
telegram: {}
openai: {}
notion:
  database_id: "db123"
  properties: {}
defaults: {}
dedup: {}
network: {}
local_input: {}
launchers:
  generate_windows_bat: true
  windows_bat_output_path: ""
  generate_macos_command: false
  macos_command_output_path: ""
linux_runtime:
  run_root: ""
"""

SECRETS_YAML = """
OPENAI_API_KEY: "k1"
TELEGRAM_BOT_TOKEN: "k2"
NOTION_API_KEY: "k3"
"""


def write_file(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


def test_load_settings_success(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    sec = tmp_path / "secrets.yaml"
    write_file(cfg, CONFIG_YAML)
    write_file(sec, SECRETS_YAML)

    settings = load_settings(cfg, sec)

    assert settings.app.app_name == "ReadQueue"
    assert settings.secrets.NOTION_API_KEY == "k3"


def test_load_settings_missing_file(tmp_path: Path) -> None:
    cfg = tmp_path / "missing.yaml"
    sec = tmp_path / "secrets.yaml"
    write_file(sec, SECRETS_YAML)

    with pytest.raises(ConfigError, match="Missing config file"):
        load_settings(cfg, sec)


def test_load_settings_missing_required_secret(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    sec = tmp_path / "secrets.yaml"
    write_file(cfg, CONFIG_YAML)
    write_file(sec, 'OPENAI_API_KEY: "x"\n')

    with pytest.raises(ConfigError, match="secrets.yaml validation failed"):
        load_settings(cfg, sec)


def test_load_settings_invalid_launcher_config(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    sec = tmp_path / "secrets.yaml"
    write_file(cfg, BAD_LAUNCHER_CONFIG_YAML)
    write_file(sec, SECRETS_YAML)

    with pytest.raises(ConfigError, match="windows_bat_output_path"):
        load_settings(cfg, sec)
