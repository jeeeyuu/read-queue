"""Models for shared ingestion pipeline results."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProcessingItemResult(BaseModel):
    """Per-URL processing result."""

    url: str
    status: str
    message: str
    error: str | None = None


class ProcessingResult(BaseModel):
    """Aggregate result for process_input_text."""

    source: str
    input_text: str
    item_results: list[ProcessingItemResult] = Field(default_factory=list)

    @property
    def url_count(self) -> int:
        return len(self.item_results)

    @property
    def success_count(self) -> int:
        return sum(1 for item in self.item_results if item.status == "success")

    @property
    def duplicate_count(self) -> int:
        return sum(1 for item in self.item_results if item.status == "duplicate")

    @property
    def warning_count(self) -> int:
        return sum(1 for item in self.item_results if item.status == "warning")

    @property
    def failure_count(self) -> int:
        return sum(1 for item in self.item_results if item.status == "failure")

    def summary_line(self) -> str:
        """Human-readable one-line summary."""

        return (
            f"Processed {self.url_count} link(s): "
            f"success={self.success_count}, duplicate={self.duplicate_count}, "
            f"warning={self.warning_count}, failure={self.failure_count}"
        )
