"""Config loading and validation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.models.config_models import AppConfig, SecretsConfig, Settings


class ConfigError(RuntimeError):
    """Raised when config file loading or validation fails."""


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Missing config file: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"Config file must be a mapping: {path}")
    return data


def _format_validation_error(prefix: str, err: ValidationError) -> str:
    lines = [f"{prefix} validation failed:"]
    for issue in err.errors():
        loc = ".".join(str(part) for part in issue.get("loc", []))
        msg = issue.get("msg", "invalid value")
        lines.append(f"- {loc}: {msg}")
    return "\n".join(lines)


def load_settings(
    config_path: str | Path = "config/config.yaml",
    secrets_path: str | Path = "config/secrets.yaml",
) -> Settings:
    """Load and validate non-secret and secret settings from YAML files."""

    config_data = _load_yaml_file(Path(config_path))
    secrets_data = _load_yaml_file(Path(secrets_path))

    try:
        app_cfg = AppConfig.model_validate(config_data)
    except ValidationError as exc:
        raise ConfigError(_format_validation_error("config.yaml", exc)) from exc

    try:
        secrets_cfg = SecretsConfig.model_validate(secrets_data)
    except ValidationError as exc:
        raise ConfigError(_format_validation_error("secrets.yaml", exc)) from exc

    return Settings(app=app_cfg, secrets=secrets_cfg)
