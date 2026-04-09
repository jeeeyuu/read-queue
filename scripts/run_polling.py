"""Entrypoint script for Telegram polling mode."""

from __future__ import annotations

from app.logging import setup_logging
from app.main import ReadingInboxApp


def main() -> None:
    app = ReadingInboxApp()
    setup_logging(app.settings.app.log_level)
    app.run_polling_forever()


if __name__ == "__main__":
    main()
