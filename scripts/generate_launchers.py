"""Generate Windows/macOS launcher wrappers from config."""

from __future__ import annotations

from app.config import load_settings
from app.services.launcher_service import generate_launchers


def main() -> int:
    settings = load_settings()
    generated = generate_launchers(settings.app)

    if not generated:
        print("No launchers generated (both launcher flags are disabled).")
        return 0

    print(f"Generated {len(generated)} launcher(s):")
    for item in generated:
        print(f"- {item.platform}: {item.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
