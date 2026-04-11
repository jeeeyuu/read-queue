"""Launcher generation helpers for Windows/macOS clipboard one-click wrappers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from app.models.config_models import AppConfig


@dataclass
class GeneratedLauncher:
    """Represents a generated launcher file."""

    platform: str
    output_path: Path


def _single_quote(text: str) -> str:
    return text.replace("'", "'\"'\"'")


def bind_runtime_root(app_config: AppConfig, runtime_root: str | Path) -> None:
    """Force runtime root to current project location during launcher generation."""

    root = str(Path(runtime_root).resolve())
    app_config.linux_runtime.project_root = root
    app_config.linux_runtime.run_root = root


def build_linux_runtime_command(app_config: AppConfig) -> str:
    """Build bash command that runs clipboard send in Linux runtime."""

    runtime = app_config.linux_runtime
    run_root = runtime.run_root or runtime.project_root
    parts = [f"cd '{_single_quote(run_root)}'"]

    if runtime.use_venv:
        activate = f"{runtime.venv_path.rstrip('/')}/bin/activate"
        parts.append(f"if [ -f '{_single_quote(activate)}' ]; then . '{_single_quote(activate)}'; fi")

    parts.append(f"{runtime.python_bin} scripts/send_clipboard.py")
    return " && ".join(parts)


def render_windows_bat(app_config: AppConfig) -> str:
    """Render Windows .bat content that calls WSL runtime.

    Success path exits immediately so the console closes on its own.
    Failure path can pause (configurable) so users can read errors.
    """

    command = build_linux_runtime_command(app_config).replace('"', r'\"')
    lines = [
        "@echo off",
        "setlocal",
        f"wsl.exe -e bash -lc \"{command}\"",
        "set EXIT_CODE=%ERRORLEVEL%",
        "if %EXIT_CODE% neq 0 (",
        "  echo ReadQueue clipboard send failed. Exit code: %EXIT_CODE%",
    ]

    if app_config.launchers.windows_pause_on_exit:
        lines.extend(
            [
                "  echo.",
                "  pause",
            ]
        )

    lines.extend(
        [
            ") else (",
            "  echo ReadQueue clipboard send finished. Exit code: %EXIT_CODE%",
            ")",
        ]
    )

    lines.append("exit /b %EXIT_CODE%")
    return "\n".join(lines) + "\n"


def render_macos_command(app_config: AppConfig) -> str:
    """Render macOS .command content."""

    command = build_linux_runtime_command(app_config)
    return f"#!/bin/bash\nset -euo pipefail\n{command}\n"


def _normalize_output_path(path_text: str) -> Path:
    """Normalize launcher output path for Linux/WSL runtime generation."""

    expanded = path_text.strip()
    drive_match = re.match(r"^([A-Za-z]):[\\/](.*)$", expanded)
    if drive_match:
        drive = drive_match.group(1).lower()
        rest = drive_match.group(2).replace("\\", "/")
        return Path(f"/mnt/{drive}/{rest}").expanduser()

    return Path(expanded).expanduser()


def _write_text_file(path_text: str, content: str) -> Path:
    path = _normalize_output_path(path_text)
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def generate_launchers(app_config: AppConfig) -> list[GeneratedLauncher]:
    """Generate launcher files based on configured output paths."""

    generated: list[GeneratedLauncher] = []

    if app_config.launchers.generate_windows_bat:
        path = _write_text_file(
            app_config.launchers.windows_bat_output_path,
            render_windows_bat(app_config),
        )
        generated.append(GeneratedLauncher(platform="windows", output_path=path))

    if app_config.launchers.generate_macos_command:
        path = _write_text_file(
            app_config.launchers.macos_command_output_path,
            render_macos_command(app_config),
        )
        path.chmod(path.stat().st_mode | 0o111)
        generated.append(GeneratedLauncher(platform="macos", output_path=path))

    return generated
