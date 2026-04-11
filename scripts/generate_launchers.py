"""Generate Windows/macOS launcher wrappers from config."""

from __future__ import annotations

from pathlib import Path

from app.config import load_settings
from app.services.launcher_service import bind_runtime_root, generate_launchers


def main() -> int:
    settings = load_settings()

    # Always bind to this project root so runtime/dev dirs stay separated.
    project_root = Path(__file__).resolve().parents[1]
    bind_runtime_root(settings.app, project_root)

    generated = generate_launchers(settings.app)

    if not generated:
        print("No launchers generated (both launcher flags are disabled).")
        return 0

    print(f"Bound runtime root: {project_root}")
    print(f"Generated {len(generated)} launcher(s):")
    for item in generated:
        print(f"- {item.platform}: {item.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
