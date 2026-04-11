"""Internal entrypoint: read clipboard and ingest into ReadQueue pipeline."""

from __future__ import annotations

import sys

from app.logging import setup_logging
from app.main import ReadingInboxApp
from app.utils.clipboard import ClipboardError, read_clipboard_text


def main() -> int:
    app = ReadingInboxApp()
    setup_logging(app.settings.app.log_level)

    if not app.settings.app.local_input.enabled:
        print("Local clipboard input is disabled in config (local_input.enabled=false).")
        return 2

    try:
        text = read_clipboard_text(os_mode=app.settings.app.local_input.os_mode)
    except ClipboardError as exc:
        print(f"Clipboard error: {exc}")
        return 2

    source_name = app.settings.app.local_input.source_name or "local"
    result = app.process_input_text(text=text, source=source_name)

    if result.url_count == 0:
        print("No URLs found in clipboard text.")
        return 2

    print(result.summary_line())
    for item in result.item_results:
        print(f"- {item.message}")

    if result.failure_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
