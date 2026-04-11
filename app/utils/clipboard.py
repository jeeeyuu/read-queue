"""Clipboard backend detection and read helpers for local one-click send."""

from __future__ import annotations

from dataclasses import dataclass
import os
import platform
import shutil
import subprocess


class ClipboardError(RuntimeError):
    """Raised when clipboard backend is unavailable or clipboard is empty."""


@dataclass(frozen=True)
class ClipboardBackend:
    """Resolved clipboard backend command."""

    name: str
    command: list[str]


def _is_wsl(system_name: str, release_name: str, env: dict[str, str]) -> bool:
    if system_name != "Linux":
        return False
    release_lower = release_name.lower()
    return "microsoft" in release_lower or "WSL_DISTRO_NAME" in env


def detect_clipboard_backend(
    os_mode: str = "auto",
    system_name: str | None = None,
    release_name: str | None = None,
    env: dict[str, str] | None = None,
    command_exists: callable | None = None,
) -> ClipboardBackend:
    """Choose clipboard backend command based on OS/runtime context."""

    system_name = system_name or platform.system()
    release_name = release_name or platform.release()
    env = env or dict(os.environ)
    command_exists = command_exists or shutil.which

    mode = (os_mode or "auto").lower()
    if mode not in {"auto", "windows", "macos", "linux", "wsl"}:
        raise ClipboardError(f"Unsupported local_input.os_mode: {os_mode}")

    resolved = mode
    if mode == "auto":
        if system_name == "Windows":
            resolved = "windows"
        elif system_name == "Darwin":
            resolved = "macos"
        elif _is_wsl(system_name, release_name, env):
            resolved = "wsl"
        else:
            resolved = "linux"

    if resolved == "windows":
        if command_exists("powershell"):
            return ClipboardBackend("powershell", ["powershell", "-NoProfile", "-Command", "Get-Clipboard"])
        raise ClipboardError("Windows clipboard backend not available: powershell")

    if resolved == "wsl":
        if command_exists("powershell.exe"):
            return ClipboardBackend(
                "wsl-powershell",
                ["powershell.exe", "-NoProfile", "-Command", "Get-Clipboard"],
            )
        raise ClipboardError("WSL clipboard backend not available: powershell.exe")

    if resolved == "macos":
        if command_exists("pbpaste"):
            return ClipboardBackend("pbpaste", ["pbpaste"])
        raise ClipboardError("macOS clipboard backend not available: pbpaste")

    if command_exists("wl-paste"):
        return ClipboardBackend("wl-paste", ["wl-paste", "--no-newline"])
    if command_exists("xclip"):
        return ClipboardBackend("xclip", ["xclip", "-selection", "clipboard", "-o"])
    if command_exists("xsel"):
        return ClipboardBackend("xsel", ["xsel", "--clipboard", "--output"])
    raise ClipboardError("Linux clipboard backend not available (tried wl-paste, xclip, xsel)")


def read_clipboard_text(os_mode: str = "auto") -> str:
    """Read current clipboard text with auto-selected backend."""

    backend = detect_clipboard_backend(os_mode=os_mode)
    proc = subprocess.run(backend.command, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise ClipboardError(f"Clipboard read failed via {backend.name}: {stderr or 'unknown error'}")

    text = (proc.stdout or "").replace("\ufeff", "").strip()
    if not text:
        raise ClipboardError("Clipboard is empty.")
    return text
