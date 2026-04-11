from __future__ import annotations

from pathlib import Path

from app.models.config_models import AppConfig
from app.services.launcher_service import generate_launchers, render_macos_command, render_windows_bat


def _base_config(tmp_path: Path) -> dict:
    return {
        "app_name": "ReadQueue",
        "environment": "dev",
        "log_level": "INFO",
        "telegram": {},
        "openai": {},
        "notion": {"database_id": "db123", "properties": {}},
        "defaults": {},
        "dedup": {},
        "network": {},
        "local_input": {},
        "launchers": {
            "generate_windows_bat": True,
            "windows_bat_output_path": str(tmp_path / "ReadQueue_send.bat"),
            "generate_macos_command": True,
            "macos_command_output_path": str(tmp_path / "ReadQueue_send.command"),
        },
        "linux_runtime": {
            "run_root": "/home/user/ReadQueue",
            "python_bin": "python3",
            "use_venv": True,
            "venv_path": ".venv",
        },
    }


def test_render_windows_bat_contains_wsl_and_send_clipboard(tmp_path: Path) -> None:
    app_cfg = AppConfig.model_validate(_base_config(tmp_path))
    content = render_windows_bat(app_cfg)

    assert "wsl.exe -e bash -lc" in content
    assert "scripts/send_clipboard.py" in content


def test_windows_bat_pauses_only_on_failure(tmp_path: Path) -> None:
    app_cfg = AppConfig.model_validate(_base_config(tmp_path))
    content = render_windows_bat(app_cfg)

    failure_idx = content.index("if %EXIT_CODE% neq 0 (")
    pause_idx = content.index("  pause")
    success_idx = content.index(") else (")

    assert failure_idx < pause_idx < success_idx


def test_render_macos_command_contains_runtime_command(tmp_path: Path) -> None:
    app_cfg = AppConfig.model_validate(_base_config(tmp_path))
    content = render_macos_command(app_cfg)

    assert content.startswith("#!/bin/bash")
    assert "scripts/send_clipboard.py" in content


def test_generate_launchers_writes_files(tmp_path: Path) -> None:
    app_cfg = AppConfig.model_validate(_base_config(tmp_path))
    generated = generate_launchers(app_cfg)

    assert len(generated) == 2
    assert (tmp_path / "ReadQueue_send.bat").exists()
    assert (tmp_path / "ReadQueue_send.command").exists()
