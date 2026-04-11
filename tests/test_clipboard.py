from __future__ import annotations

import pytest

from app.utils.clipboard import ClipboardError, detect_clipboard_backend


def _exists(commands: set[str]):
    return lambda cmd: "/usr/bin/" + cmd if cmd in commands else None


def test_detect_wsl_prefers_powershell_exe() -> None:
    backend = detect_clipboard_backend(
        os_mode="auto",
        system_name="Linux",
        release_name="5.15.90.1-microsoft-standard-WSL2",
        env={"WSL_DISTRO_NAME": "Ubuntu"},
        command_exists=_exists({"powershell.exe"}),
    )
    assert backend.name == "wsl-powershell"
    assert backend.command[0] == "powershell.exe"


def test_detect_linux_backend_fallback_order() -> None:
    backend = detect_clipboard_backend(
        os_mode="linux",
        system_name="Linux",
        release_name="6.8.0",
        env={},
        command_exists=_exists({"xclip"}),
    )
    assert backend.name == "xclip"


def test_detect_linux_backend_missing() -> None:
    with pytest.raises(ClipboardError, match="Linux clipboard backend"):
        detect_clipboard_backend(
            os_mode="linux",
            system_name="Linux",
            release_name="6.8.0",
            env={},
            command_exists=_exists(set()),
        )
